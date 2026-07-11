#!/usr/bin/env python3
"""Validate a model (`project-map.json`) — `coyodex validate`.

Two layers:

  1. STRUCTURE — `model.load_model` already validated shape/types/id-prefixes. This module starts
     where structure ends.
  2. SEMANTICS — every referenced ID resolves, hierarchy sound (right-kind parents, no cycles,
     deep-nest advisory), HP steps name their use case, flow actors resolve to Roles, dep Kinds in
     the closed vocabulary, domain-card completeness, plus every advisory nudge (altitude, empty
     groups, unowned entities, orphan deps honoring the `deployment_linked` marker) and the opt-in
     repo-reading checks (`--check-sources` anchors + entity grounding, `--check-coverage`
     compression + under-harvest, with `--repo` carried over).

One extra check: the committed markdown VIEW must match the model (it is generated, never edited)
— a stale or hand-edited `project-map.md` next to the JSON is flagged.

Stdlib-only.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

from coyodex import grammar
from coyodex.anchors import DIR_ANCHOR as _DIR_ANCHOR, FILE_ANCHOR as _ANCHOR_LINE
from coyodex.model import ID_ARRAYS, ID_SHAPE, ModelError, ProjectModel, all_elements, load_model
from coyodex.validate_analysis import (
    _ALTITUDE_MIN,
    _COVERAGE_SAMPLE,
    _ISOLATED_FRACTION,
    _ISOLATED_MIN,
    _ISOLATED_MIN_ENTITIES,
    _LIST_ITEM,
    _REF_INLINE,
    _REF_LINK,
    _UNCOVERED_FRACTION,
    _UNCOVERED_MIN,
    _is_non_entity_type,
    _resolve_source_file,
    _source_roots,
    _type_covered,
    _where_href,
    check_hierarchy,
    compression_coverage_from_refs,
    granularity_advisory,
    strip_anchor,
)

_WRITE_VERBS = ("persists", "writes")  # ownership verbs for the unowned-entities nudge (as in v1)


# ── shared extraction ────────────────────────────────────────────────────────────────────────────

def _strings(value: object, skip_keys: frozenset[str] = frozenset({"format"})) -> list[str]:
    """Every string stored in the model (recursively), the analog of scanning the whole markdown
    document — ID references and path references live anywhere in authored text."""
    out: list[str] = []
    if hasattr(value, "__dataclass_fields__"):
        from dataclasses import fields
        for f in fields(value):  # type: ignore[arg-type]
            if f.name not in skip_keys:
                out.extend(_strings(getattr(value, f.name)))
    elif isinstance(value, list):
        for v in value:
            out.extend(_strings(v))
    elif isinstance(value, dict):
        for v in value.values():
            out.extend(_strings(v))
    elif isinstance(value, str):
        out.append(value)
    return out


def _parents(m: ProjectModel) -> dict[str, str]:
    """child id -> parent id, across both forests (C→S, S→S, SD→SD, E→SD) — single-source, on the
    child."""
    out: dict[str, str] = {}
    for c in m.components:
        if c.subsystem:
            out[c.id] = c.subsystem
    for s in m.subsystems:
        if s.parent:
            out[s.id] = s.parent
    for sd in m.subdomains:
        if sd.parent:
            out[sd.id] = sd.parent
    for e in m.entities:
        if e.subdomain:
            out[e.id] = e.subdomain
    return out


def _first_link_of(el: object, cells: list[str | None]) -> str | None:
    """A definition's first markdown link, across a set of candidate free-text cells."""
    link = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
    for c in cells:
        if c:
            hit = link.search(c)
            if hit:
                return hit.group(1).strip()
    return None


def _is_subsystem_id(i: str) -> bool:
    return i.startswith("S") and not i.startswith("SD")


# ── semantic checks ──────────────────────────────────────────────────────────────────────────────

def _check_ids(m: ProjectModel) -> list[str]:
    problems: list[str] = []
    counts: dict[str, int] = {}
    for attr in ID_ARRAYS:
        if attr == "happy_path":
            continue  # a use case may occupy several HP positions; HP ids ride their own check
        for el in getattr(m, attr):
            counts[el.id] = counts.get(el.id, 0) + 1
    duplicates = sorted(i for i, n in counts.items() if n > 1)
    if duplicates:
        problems.append(f"Duplicate element definitions: {', '.join(duplicates)}")

    # Pointer fields must be well-shaped ids (the `S12a` class — invisible to the reference scan
    # because a suffixed token is not an ID token at all).
    pointers: list[tuple[str, str, str | None]] = (
        [(c.id, "subsystem", c.subsystem) for c in m.components]
        + [(s.id, "parent", s.parent) for s in m.subsystems]
        + [(sd.id, "parent", sd.parent) for sd in m.subdomains]
        + [(e.id, "subdomain", e.subdomain) for e in m.entities]
        + [(g.id, "uc", g.uc) for g in m.happy_path]
        + [(e.id, "relation target", r.target) for e in m.entities for r in e.relations]
    )
    for owner, field_name, val in pointers:
        if val is not None and not ID_SHAPE.match(val):
            problems.append(f"{owner}: {field_name} '{val}' is not a valid schema ID "
                            f"(prefix + digits only)")
    for e in m.edges:
        for end in (e.src, e.dst):
            if not ID_SHAPE.match(end):
                problems.append(f"Edge {e.src} → {e.dst}: endpoint '{end}' is not a valid schema ID")
    return problems


# An explicit in-prose cross-reference: `[[C12]]`. A BARE id-shaped token in prose or an anchor
# (the PKCE value `S256`, a `D3`/`C4` library name, an `infra/S3/` path segment) is NOT a reference —
# `_referenced_ids` reads ids only from typed id fields and these `[[...]]` markers, so a domain string
# is never misread as a dangling ref (the class the whole-document scan used to false-positive on).
_BRACKET_REF = re.compile(r"\[\[([^\]]+)\]\]")


def _referenced_ids(m: ProjectModel) -> set[str]:
    """The ids the model genuinely cross-references, gathered ONLY from typed id-bearing fields and
    explicit `[[ID]]` prose markers — never scanned out of free prose or anchor strings."""
    refs: set[str] = set()
    for c in m.components:
        if c.subsystem:
            refs.add(c.subsystem)
    for s in m.subsystems:
        if s.parent:
            refs.add(s.parent)
    for sd in m.subdomains:
        if sd.parent:
            refs.add(sd.parent)
    for g in m.happy_path:
        if g.uc:
            refs.add(g.uc)
    for u in m.use_cases:
        refs.update(u.actors)                        # a use case's actors are role ids
    for f in m.flows:
        if f.uc:
            refs.add(f.uc)
        for st in f.steps:
            for end in (st.src, st.dst):              # backbone-element OR role-id (actor step) endpoints
                if end and (grammar.is_step_id(end) or grammar.is_role_id(end)):
                    refs.add(end)
    for e in m.edges:
        refs.add(e.src)
        refs.add(e.dst)
    for en in m.entities:
        if en.subdomain:
            refs.add(en.subdomain)
        for r in en.relations:
            if r.target:
                refs.add(r.target)
        for fld in en.fields:
            refs |= grammar.fk_targets(fld.markers)            # FK→En markers
            refs.update(grammar.ID_TOKEN.findall(fld.type))    # entity-typed field, e.g. `auth:E7`
    for r in m.roles:
        refs.update(grammar.ID_TOKEN.findall(r.drives))        # `drives` holds the UC ids a role drives
    for s in _strings(m):                                      # deliberate prose cross-refs `[[ID]]`
        for inner in _BRACKET_REF.findall(s):
            tok = inner.strip()
            if grammar.ID_TOKEN.fullmatch(tok):
                refs.add(tok)
    return refs


def _check_references(m: ProjectModel) -> list[str]:
    """Every cross-referenced ID resolves to a defined element. References are read only from typed id
    fields + `[[ID]]` markers (`_referenced_ids`), never scanned out of prose/anchors — so a domain
    string shaped like an id (`S256`, `D3`) is never a false dangling ref. Additivity: stray S/SD refs
    are ignored while the map has no grouping/subdomains."""
    defined = set(all_elements(m)) | {g.id for g in m.happy_path}
    referenced = _referenced_ids(m)
    parents = _parents(m)
    grouping_present = (any(_is_subsystem_id(i) for i in defined)
                        or any(_is_subsystem_id(p) for p in parents.values()))
    subdomains_present = (any(i.startswith("SD") for i in defined)
                          or any(p.startswith("SD") for p in parents.values()))

    def suppress(r: str) -> bool:
        if r.startswith("SD"):
            return not subdomains_present
        if r.startswith("S"):
            return not grouping_present
        return False

    unresolved = sorted(r for r in referenced - defined if not suppress(r))
    return [f"References to undefined IDs: {', '.join(unresolved)}"] if unresolved else []


def _check_hp(m: ProjectModel) -> list[str]:
    missing = [g.id for g in m.happy_path if not g.uc]
    return ([f"Happy Path steps missing a use-case reference (`uc`): {', '.join(missing)}"]
            if missing else [])


def _check_flows(m: ProjectModel) -> list[str]:
    problems: list[str] = []
    counts: dict[str, int] = {}
    for f in m.flows:
        counts[f.uc] = counts.get(f.uc, 0) + 1
    dups = sorted(uc for uc, c in counts.items() if c > 1)
    if dups:
        problems.append("Use cases with more than one T6 flow block (each use case has exactly one "
                        f"flow): {', '.join(dups)}")
    role_ids = {r.id for r in m.roles}
    for f in m.flows:
        for st in f.steps:
            tag = f"{f.uc} flow step {st.n}"
            if not st.src or not st.dst:
                problems.append(f"{tag} is missing an endpoint (`from → to` needs both)")
                continue
            if not st.phrase.strip():
                problems.append(f"{tag} has no action text (`phrase`) — every step describes what "
                                "happens at that point; it is not derived from the backbone edge")
            if role_ids:  # a non-backbone endpoint is an actor step — it must be a defined Role id
                for end in (st.src, st.dst):
                    if not grammar.is_step_id(end) and end not in role_ids:
                        problems.append(f"{tag}: actor '{end}' is not a defined Role id")
    return problems


def _check_roles(m: ProjectModel) -> list[str]:
    if m.roles and all(not r.kind.strip() for r in m.roles):
        return ["Roles carry no Kind (human/service) — every role states one"]
    return []


def _check_actors(m: ProjectModel) -> list[str]:
    """Loud guard (the anti-silent-no-op): when roles are defined, EVERY use case must name at least one
    actor (a role id). Otherwise `check_actor_attribution` has nothing to compare and silently passes —
    the exact failure the role-id model exists to prevent. A roles-less map legitimately has no actors."""
    if not m.roles:
        return []
    missing = [u.id for u in m.use_cases if not u.actors]
    if not missing:
        return []
    return [f"Use cases with no actor (roles are defined, so each names ≥1 role id): {', '.join(missing)}"]


def _check_dep_kinds(m: ProjectModel) -> list[str]:
    return [f"{d.id} has an invalid dependency Kind '{d.kind}' — use one of: "
            f"{', '.join(grammar.DEP_KINDS)}"
            for d in m.deps if d.kind and d.kind.strip().lower() not in grammar.DEP_KINDS]


def _check_edges(m: ProjectModel) -> tuple[list[str], list[str]]:
    problems: list[str] = []
    warnings: list[str] = []
    for e in m.edges:
        if not e.verb.strip():
            problems.append(f"Edge {e.src} → {e.dst} has an empty Verb")
        has_where = bool(e.where)                          # a PRESENT-but-malformed `where` (incl. a
        if not has_where and not e.no_call_site:           # whitespace-only one) is owned by the anchor-
                                                           # format gate; here we own only the ABSENT case
            problems.append(
                f"{e.src} → {e.dst}: no `Where` call-site anchor — add the bare `path:line` where {e.src} "
                f"invokes {e.dst} (a flow arrow opens it to drill to code), or set `no_call_site` if this "
                "relationship has no single call site (event-driven / shared-state / config-wired coupling)")
        elif has_where and e.no_call_site:
            warnings.append(f"{e.src} → {e.dst}: `no_call_site` is set but a `Where` is present — "
                            "drop one so the intent is unambiguous")
    return problems, warnings


def _check_domain_cards(m: ProjectModel) -> tuple[list[str], list[str]]:
    problems: list[str] = []
    warnings: list[str] = []
    directed: set[tuple[str, str]] = set()
    backing = {e.id: [(f.name, f.type, grammar.fk_targets(f.markers)) for f in e.fields]
               for e in m.entities}
    for e in m.entities:
        if not e.meaning:
            problems.append(f"Domain card {e.id} is missing a MEANING line")
        if not e.source:
            problems.append(f"Domain card {e.id} is missing a SOURCE link")
        if not e.fields:
            problems.append(f"Domain card {e.id} has no FIELDS")
        for f in e.fields:
            if not f.type:
                problems.append(f"Domain card {e.id} field '{f.name}' has no type")
        seen_pairs: set[tuple[str, str]] = set()
        for r in e.relations:
            if r.verb.lower() in grammar.REL_ALIAS:
                problems.append(f"Domain card {e.id}: relation verb '{r.verb}' is a non-canonical "
                                f"alias — use '{grammar.REL_ALIAS[r.verb.lower()]}'")
            if (r.src_card is None) != (r.dst_card is None):
                problems.append(f"Domain card {e.id}: relation '{r.verb} … {r.target}' has a "
                                f"half-stated cardinality — state both sides (`sc→dc`) or neither")
            if (r.verb, r.target) in seen_pairs:
                problems.append(f"Domain card {e.id} declares the relation "
                                f"'{r.verb} … {r.target}' twice")
            seen_pairs.add((r.verb, r.target))
            directed.add((e.id, r.target))
            kind = grammar.REL_KIND.get(r.verb.lower(), "association")
            if kind == "association" and r.target in backing and not r.how:
                names, _side = grammar.resolve_backing(e.id, r.target, backing[e.id],
                                                        backing[r.target])
                if not names:
                    warnings.append(
                        f"Domain card {e.id}: relation '{r.verb} … {r.target}' is not backed by a "
                        f"field and has no {{…}} note — mark the implementing field `FK→{r.target}` "
                        f"(or `FK→{e.id}` on {r.target}), or add a `{{how}}` note explaining the link")
    for a, b in directed:
        if a < b and (b, a) in directed:
            problems.append(f"Relation between {a} and {b} is declared on both cards — author it "
                            f"on one side only")
    return problems, warnings


# The canonical anchor shapes live in one place now — `coyodex.anchors` (method/model.md's 'Anchor
# formats'): a repo-relative file ref with an optional `:line`/`:line-line` (extension optional, so
# `Dockerfile:1` is valid), or a bare directory ref (`_DIR_ANCHOR`) additionally valid for `source`.


def _check_anchor_format(m: ProjectModel) -> list[str]:
    """Every source-location field matches the one shape it's required to have."""
    problems: list[str] = []

    def bad_file(label: str, val: str | None) -> None:
        if val and not _ANCHOR_LINE.match(val):
            problems.append(f"{label}: '{val}' is not a valid `path:line` anchor")

    def bad_anchor(label: str, val: str | None) -> None:  # a file OR a directory
        if val and not (_ANCHOR_LINE.match(val) or _DIR_ANCHOR.match(val)):
            problems.append(f"{label}: '{val}' is not a valid anchor (bare `path:line` or `path/`)")

    for c in m.components:
        bad_anchor(f"{c.id} source", c.source)
        bad_file(f"{c.id} entry_point", c.entry_point)
    for d in m.deps:
        bad_file(f"{d.id} where_configured", d.where_configured)
    for e in m.edges:
        bad_file(f"{e.src} → {e.dst} where", e.where)
    for ep in m.entry_points:
        bad_file(f"entry_points[{ep.component} {ep.kind}].source", ep.source)
    for e in m.entities:
        bad_anchor(f"{e.id} source", e.source)
    for g in m.glossary:
        bad_anchor(f"glossary '{g.term}' source", g.source)
    for group in (*m.subsystems, *m.subdomains):
        bad_anchor(f"{group.id} source", group.source)
    return problems


# `extra` is freeform by design — but the moment a key's shape is enforced (below) or the method
# names it as a convention, it has already become a de facto field, so it graduates to a real one
# instead of staying a "standardized" extra column. These are the promoted names' old spellings —
# authoring any of them under `extra` is a mistake, not a valid alternative spelling.
_PROMOTED_EXTRA_KEYS = {
    "files": "files", "files_count": "files", "members": "files",
    "evidence": "evidence",
    "package": "package", "sdk": "package", "client_library": "package",
    "alternative": "alternative", "standalone_alternative": "alternative",
}
_FORBIDDEN_EXTRA_KEYS = {"loc"}  # mechanical (line count) — compute it, don't hand-author it
_DEPLOYMENT_FLAVORED_EXTRA_KEYS = {
    "flags", "modes", "scaling", "sticky_sessions", "mode", "api_key", "noop_without", "wired_by",
}


def _check_extra_conventions(m: ProjectModel) -> tuple[list[str], list[str]]:
    """`extra` may only hold what the method has no opinion about — see the module constants above
    for the promoted/forbidden/advisory key lists."""
    problems: list[str] = []
    warnings: list[str] = []
    for el in (*m.components, *m.deps):
        for key in el.extra:
            if key in _PROMOTED_EXTRA_KEYS:
                problems.append(f"{el.id} extra.{key}: retired — use the top-level "
                                f"`{_PROMOTED_EXTRA_KEYS[key]}` field instead")
            elif key in _FORBIDDEN_EXTRA_KEYS:
                problems.append(f"{el.id} extra.{key}: not hand-authored — compute it, don't author it")
            elif key in _DEPLOYMENT_FLAVORED_EXTRA_KEYS:
                warnings.append(f"{el.id} extra.{key}: looks like deployment/config info — check "
                                f"whether it belongs in the Deployment or Config table instead")
    return problems, warnings


def _check_evidence(m: ProjectModel) -> list[str]:
    """`evidence[].file` is a bare `path:line` anchor (method/model.md's 'Anchor formats');
    `evidence[].why` must be a real explanation, not left blank."""
    problems: list[str] = []
    for el in (*m.components, *m.deps):
        for i, ev in enumerate(el.evidence):
            if not _ANCHOR_LINE.match(ev.file):
                problems.append(f"{el.id} evidence[{i}].file: '{ev.file}' is not a valid "
                                f"`path:line` anchor")
            if not ev.why.strip():
                problems.append(f"{el.id} evidence[{i}].why: must be a non-empty explanation")
    return problems


def _check_altitude(m: ProjectModel) -> list[str]:
    out: list[str] = []
    for c in m.components:
        n = sum(1 for s in (seg.strip() for seg in c.purpose.split(",")) if _LIST_ITEM.match(s))
        if n >= _ALTITUDE_MIN:
            out.append(f"Component {c.id} lists {n} sub-units in its Purpose — if these are real "
                       f"units, consider promoting {c.id} to a subsystem (its members then get "
                       f"their own drill level)")
    return out


def _anchor_pairs(m: ProjectModel) -> list[tuple[str, str]]:
    """(label, href) for every drill-to-code anchor: each edge's `Where`, each element definition's
    first link (plus the canonical `anchor`), each card's SOURCE. Off-repo URLs excluded. Used by
    the opt-in `--check-sources` existence check — shape validity is `_check_anchor_format`'s job,
    not this collector's."""
    url = re.compile(r"^[a-z][a-z0-9+.-]*://", re.I)
    out: list[tuple[str, str]] = []
    for e in m.edges:
        href = _where_href(e.where or "")
        if href:
            out.append((f"{e.src} → {e.dst} `Where`", href))
    for u in m.use_cases:
        href = _first_link_of(u, [u.name, u.trigger_outcome])  # actors are role ids now, not a link cell
        if href and not url.match(href):
            out.append((u.id, href))
    for group in (*m.subsystems, *m.subdomains):
        if group.source and not url.match(group.source):
            out.append((f"{group.id} source", group.source))
    for c in m.components:
        if c.source and not url.match(c.source):
            out.append((f"{c.id} source", c.source))
        href = c.entry_point or _first_link_of(c, [c.purpose, c.depends_on,
                                  *(v for v in c.extra.values() if isinstance(v, str))])
        if href and not url.match(href):
            out.append((c.id, href))
    for d in m.deps:
        href = d.where_configured or _first_link_of(d, [d.name, d.type, d.used_for,
                                  *(v for v in d.extra.values() if isinstance(v, str))])
        if href and not url.match(href):
            out.append((d.id, href))
    for e in m.entities:
        if e.source and not url.match(e.source):
            out.append((e.id, e.source))
    for g in m.glossary:
        if g.source and not url.match(g.source):
            out.append((f"glossary '{g.term}'", g.source))
    for ep in m.entry_points:
        if ep.source and not url.match(ep.source):
            out.append((f"entry_points[{ep.component} {ep.kind}]", ep.source))
    return out


def check_anchor_existence_model(m: ProjectModel, roots: list[Path]) -> list[str]:
    out: list[str] = []
    for label, href in _anchor_pairs(m):
        rel = strip_anchor(href)
        is_dir = rel.endswith("/")
        rel = rel.rstrip("/")
        if not rel:
            continue
        ok = any((r / rel).is_dir() if is_dir else (r / rel).is_file() for r in roots)
        if not ok:
            out.append(f"{label}: '{href}' does not resolve to a "
                       f"{'directory' if is_dir else 'file'} in the repo")
    return out


def check_entity_sources_model(m: ProjectModel, roots: list[Path]) -> list[str]:
    """Each entity's name must appear in its SOURCE file — the anti-synthesized-entity gate, a
    lenient token-substring match against the file's text."""
    problems: list[str] = []
    for e in m.entities:
        if not e.source or e.name == e.id:
            continue
        src = _resolve_source_file(e.source, roots)
        if src is None:
            continue
        try:
            code = src.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        tokens = re.findall(r"[A-Za-z_]\w{2,}", e.name)
        if tokens and not any(tok.lower() in code for tok in tokens):
            rel = strip_anchor(e.source)
            problems.append(f"Domain card {e.id} '{e.name}' is not defined in its SOURCE ({rel}) — "
                            f"likely synthesized or a wrong anchor; entities must be real named types")
    return problems


def referenced_paths(m: ProjectModel, root: Path) -> set[str]:
    """Repo-relative paths the model points at, extracted from every stored string (link targets +
    inline paths), kept only when they exist. The model-native analog of the retired markdown
    reader's per-map referenced-paths scan."""
    cands: set[str] = set()
    for s in _strings(m):
        cands.update(_REF_LINK.findall(s))
        cands.update(_REF_INLINE.findall(s))
    rootstr = str(root)
    refs: set[str] = set()
    for c in cands:
        c = strip_anchor(c.strip())
        if c.startswith("file://"):
            c = c[7:]
        if c.startswith(rootstr):
            c = c[len(rootstr):]
        c = c.strip("/")
        if c and not c.startswith(".coyodex") and (root / c).exists():
            refs.add(c)
    return refs


def check_domain_coverage_model(m: ProjectModel, roots: list[Path]) -> list[str]:
    """The under-harvest advisory, ported: (a) relation-isolated entities (model-only), (b) named
    Python types in the entities' source dirs with no entity card (stdlib `ast` re-measurement).
    v2 refinement: a type explicitly listed in `non_entity_types` is excluded by NAME — the model's
    plumbing marker — with the v1 suffix/base heuristic kept as the fallback."""
    if not m.entities:
        return []
    out: list[str] = []
    related: set[str] = set()
    for e in m.entities:
        for r in e.relations:
            related.add(e.id)
            related.add(r.target)
    ids = [e.id for e in m.entities]
    isolated = [i for i in ids if i not in related]
    n = len(ids)
    if (n >= _ISOLATED_MIN_ENTITIES and len(isolated) >= _ISOLATED_MIN
            and len(isolated) > _ISOLATED_FRACTION * n):
        out.append(
            f"Isolated entities: {len(isolated)} of {n} entity cards have NO E↔E relation "
            f"({round(100 * len(isolated) / n)}% of the domain model) — a sparse class graph is the "
            f"signature of an under-harvested domain model (did one T5 harvest agent author "
            f"per-entity RELATIONS?): {', '.join(isolated[:_COVERAGE_SAMPLE])}"
            + (f", +{len(isolated) - _COVERAGE_SAMPLE} more" if len(isolated) > _COVERAGE_SAMPLE else "")
        )
    domain_dirs: set[Path] = set()
    for e in m.entities:
        if e.source:
            src = _resolve_source_file(e.source, roots)
            if src is not None:
                domain_dirs.add(src.parent)
    marked = {t.name for t in m.non_entity_types}
    types: dict[str, Path] = {}
    for d in sorted(domain_dirs):
        for f in sorted(d.glob("*.py")):
            try:
                tree = ast.parse(f.read_text(encoding="utf-8", errors="ignore"))
            except (OSError, SyntaxError, ValueError):
                continue
            for node in tree.body:
                if (isinstance(node, ast.ClassDef) and node.name not in marked
                        and not _is_non_entity_type(node)):
                    types.setdefault(node.name, f)
    if types:
        entity_names = [e.name for e in m.entities if e.name != e.id]
        uncovered = sorted(t for t in types if not _type_covered(t, entity_names))
        if len(uncovered) >= _UNCOVERED_MIN and len(uncovered) >= _UNCOVERED_FRACTION * len(types):
            shown = ", ".join(uncovered[:_COVERAGE_SAMPLE]) + (
                f", +{len(uncovered) - _COVERAGE_SAMPLE} more"
                if len(uncovered) > _COVERAGE_SAMPLE else "")
            out.append(
                f"Under-harvested domain model: {len(uncovered)} of {len(types)} named types in the "
                f"entities' source dirs have no entity card (possible under-harvested domain model; "
                f"Python types only, measured at validate time): {shown}"
            )
    return out


def _check_view_fresh(m: ProjectModel, model_path: Path) -> list[str]:
    """The committed markdown view must equal the regenerated one — it is a generated artifact
    (maintainer decision: the view IS committed for readable diffs, so staleness must be visible)."""
    from coyodex.views import model_to_markdown
    view = model_path.with_name("project-map.md")
    if not view.exists():
        return [f"generated markdown view missing next to the model — write it with "
                f"`coyodex render {model_path.name} {view.name}`"]
    if view.read_text(encoding="utf-8") != model_to_markdown(m):
        return [f"{view.name} differs from the view generated from {model_path.name} — it is a "
                f"GENERATED file (stale, or hand-edited); regenerate with `coyodex render`"]
    return []


# ── orchestration ────────────────────────────────────────────────────────────────────────────────

def validate_model(m: ProjectModel, model_path: Path | None = None, *,
                   check_sources: bool = False, check_coverage: bool = False,
                   repo_root: Path | None = None) -> tuple[list[str], list[str]]:
    """Every semantic check over a structurally-valid model; returns (problems, warnings) exactly
    like the v1 validator did, so the profiler and the CLI share one orchestration."""
    if (check_sources or check_coverage) and model_path is None and repo_root is None:
        raise ValueError("model_path or repo_root is required when check_sources/check_coverage is set")
    problems: list[str] = []
    warnings: list[str] = []
    defined = set(all_elements(m)) | {g.id for g in m.happy_path}

    problems.extend(_check_ids(m))
    problems.extend(_check_references(m))
    problems.extend(_check_hp(m))
    problems.extend(_check_flows(m))
    problems.extend(_check_roles(m))
    problems.extend(_check_actors(m))
    problems.extend(_check_dep_kinds(m))
    edge_problems, edge_warnings = _check_edges(m)
    problems.extend(edge_problems)
    warnings.extend(edge_warnings)
    card_problems, card_warnings = _check_domain_cards(m)
    problems.extend(card_problems)
    warnings.extend(card_warnings)
    problems.extend(_check_anchor_format(m))
    problems.extend(_check_evidence(m))
    extra_problems, extra_warnings = _check_extra_conventions(m)
    problems.extend(extra_problems)
    warnings.extend(extra_warnings)

    roots = _source_roots(model_path, repo_root) if model_path is not None else (
        [repo_root.resolve()] if repo_root is not None else [])
    if check_sources:
        problems.extend(check_entity_sources_model(m, roots))
        # A nonexistent-file anchor means a wrong repo-root prefix or a stale path reached the map — a
        # real error, not a nudge. Blocking (B3) so `validate --check-sources` is the deterministic
        # backstop for the source-side prefix rule (a missing file can never slip through all-green).
        problems.extend(check_anchor_existence_model(m, roots))

    parents = _parents(m)
    hier_problems, hier_warnings = check_hierarchy(parents, defined)
    problems.extend(hier_problems)
    warnings.extend(hier_warnings)
    warnings.extend(_check_altitude(m))
    if check_coverage:
        walk_root = repo_root if repo_root is not None else (
            model_path.resolve().parent.parent if model_path is not None else None)
        if walk_root is not None:
            warnings.extend(compression_coverage_from_refs(
                referenced_paths(m, walk_root.resolve()), walk_root))
            # The granularity anchor: component (leaf) count vs the code-derived expectation E —
            # re-computed from the tree here (GR4), advisory-only, silent inside the ±40% band.
            warnings.extend(granularity_advisory(len(m.components), walk_root))
        warnings.extend(check_domain_coverage_model(m, roots))

    # Redundant nesting (a group whose only child is a group of the same kind).
    child_count: dict[str, int] = {}
    only_child: dict[str, str] = {}
    for c, p in parents.items():
        child_count[p] = child_count.get(p, 0) + 1
        only_child[p] = c
    redundant = sorted(
        p for p, n in child_count.items() if n == 1
        and ((_is_subsystem_id(p) and _is_subsystem_id(only_child[p]))
             or (p.startswith("SD") and only_child[p].startswith("SD")))
    )
    if redundant:
        warnings.append("Groups whose only child is another group of the same kind (redundant "
                        f"nesting level): {', '.join(redundant)}")

    # Grouping guards + nudges (unchanged semantics from v1).
    comp_ids = {c.id for c in m.components}
    if m.subsystems and comp_ids and not any(c.subsystem for c in m.components):
        problems.append("Subsystems (S) defined but no component is assigned to one — every "
                        "component's `subsystem` is empty")
    assigned_s = {c.subsystem for c in m.components if c.subsystem}
    if assigned_s:
        parent_s = {s.parent for s in m.subsystems if s.parent}
        empty_s = sorted(s.id for s in m.subsystems
                         if s.id not in assigned_s and s.id not in parent_s)
        if empty_s:
            warnings.append("Subsystems with no members (empty box — no component assigned, no "
                            f"child subsystem): {', '.join(empty_s)}")
    if m.subdomains and m.entities and not any(e.subdomain for e in m.entities):
        problems.append("Subdomains (SD) defined but no entity is assigned to one — every entity's "
                        "`subdomain` is empty")
    if m.subdomains and any(e.subdomain for e in m.entities):
        ungrouped = sorted(e.id for e in m.entities if not e.subdomain)
        if ungrouped:
            warnings.append(f"Entities with no SUBDOMAIN (ungrouped / top-level): "
                            f"{', '.join(ungrouped)}")
    assigned_sd = {e.subdomain for e in m.entities if e.subdomain}
    parent_sd = {sd.parent for sd in m.subdomains if sd.parent}
    empty_sd = sorted(sd.id for sd in m.subdomains
                      if sd.id not in assigned_sd and sd.id not in parent_sd)
    if empty_sd:
        warnings.append(f"Subdomains with no entities: {', '.join(empty_sd)}")

    # Ownership + orphan-dep nudges over the backbone.
    owned = {e.dst for e in m.edges
             if e.src.startswith("C") and e.dst.startswith("E") and e.verb.lower() in _WRITE_VERBS}
    if owned and m.entities:
        embedded = {r.target for ent in m.entities for r in ent.relations
                    if grammar.REL_KIND.get(r.verb.lower()) in ("composition", "aggregation")}
        unowned = sorted(e.id for e in m.entities if e.id not in owned and e.id not in embedded)
        if unowned:
            shown = ", ".join(unowned[:12]) + (f", +{len(unowned) - 12} more"
                                               if len(unowned) > 12 else "")
            warnings.append(f"Entities with no owning component (no persists/writes C→E edge): {shown}")
    if m.edges:
        targets = {e.dst for e in m.edges}
        # v2: a dep marked deployment_linked has no code call site BY DECLARATION — the nudge must
        # not pressure anyone to invent an edge for it (the audit→Elastic false-edge class).
        orphan_deps = sorted(d.id for d in m.deps
                             if d.id not in targets and not d.deployment_linked)
        if orphan_deps:
            shown = ", ".join(orphan_deps[:12]) + (f", +{len(orphan_deps) - 12} more"
                                                   if len(orphan_deps) > 12 else "")
            warnings.append(f"External deps with no incoming edge (un-traced — which component "
                            f"uses each?): {shown}")

    if model_path is not None:
        warnings.extend(_check_view_fresh(m, model_path))
    return problems, warnings


# ── CLI ──────────────────────────────────────────────────────────────────────────────────────────

def _inventory(m: ProjectModel) -> str:
    counts = {"UC": len(m.use_cases), "HP": len(m.happy_path), "S": len(m.subsystems),
              "C": len(m.components), "D": len(m.deps), "SD": len(m.subdomains),
              "E": len(m.entities)}
    return ", ".join(f"{k}:{v}" for k, v in sorted(counts.items()) if v)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "-h" in argv or "--help" in argv:
        print("usage: coyodex validate [--check-sources] [--check-coverage] [--repo <root>] "
              "[.coyodex/project-map.json]\n\n"
              "Validate a model: structural schema validation, then the semantic\n"
              "checks (IDs resolve, hierarchy sound, cards complete, view fresh, …).")
        return 0

    repo_root: Path | None = None
    if "--repo" in argv:
        i = argv.index("--repo")
        if i + 1 >= len(argv):
            print("ERROR: --repo needs a path (the analyzed repo's root)", file=sys.stderr)
            return 2
        repo_root = Path(argv[i + 1])
        del argv[i:i + 2]
        if not repo_root.is_dir():
            print(f"ERROR: --repo {repo_root} is not a directory", file=sys.stderr)
            return 2
    check_sources = "--check-sources" in argv
    check_coverage = "--check-coverage" in argv
    unknown = [a for a in argv if a.startswith("-")
               and a not in ("--check-sources", "--check-coverage")]
    if unknown:
        print(f"ERROR: unknown option(s): {', '.join(unknown)}", file=sys.stderr)
        return 2
    args = [a for a in argv if not a.startswith("-")]
    path = Path(args[0] if args else ".coyodex/project-map.json")
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 1
    try:
        m = load_model(path.read_text(encoding="utf-8"))
    except ModelError as e:
        print("\nVALIDATION FAILED (schema):")
        print(f"  - {e}")
        return 1
    problems, warnings = validate_model(m, path, check_sources=check_sources,
                                        check_coverage=check_coverage, repo_root=repo_root)
    print(f"Inventory — {_inventory(m)}")
    if warnings:
        print("\nVALIDATION WARNINGS (non-blocking):")
        for w in warnings:
            print(f"  - {w}")
    if problems:
        print("\nVALIDATION FAILED:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("Schema OK — structure valid, all IDs defined once, all references resolve, every HP "
          "step names a use case, every flow step well-formed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
