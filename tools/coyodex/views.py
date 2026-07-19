#!/usr/bin/env python3
"""Generated views of the model: model → markdown, and model → graph (the viewer's input).

The markdown view is the READABLE, COMMITTED rendering of `project-map.json` (canonical section
order, template-shaped tables, deterministic output) — never hand-edited; `coyodex validate` warns
when the committed copy is stale. The graph view feeds the viewer bundle builder
(`gen_viewer.build_view_bundle`, served by `coyodex serve`) its `GraphDict` input, built straight
from the model.

Stdlib-only. Both functions are pure (same model → same bytes).
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import asdict

from coyodex import grammar
from coyodex.model import (
    Component,
    Dep,
    Entity,
    EvidenceItem,
    FlowStep,
    Group,
    ProjectModel,
    TestRow,
    UseCase,
    all_elements,
)
from coyodex.validate_analysis import strip_anchor
from coyodex.viewer.build_graph import (
    LINK,
    Edge as GraphEdge,
    HappyStep as GraphHappyStep,
    GraphDict,
    Node,
    TestTarget,
    _ensure_default_subsystem,
    _line_of,
    _role_kind,
)

# ── markdown view ────────────────────────────────────────────────────────────────────────────────

_GENERATED_NOTICE = (
    "<!-- GENERATED VIEW — do not edit. The source of truth is project-map.json; regenerate this\n"
    "     file with `coyodex render project-map.json project-map.md`. -->")


def _esc(cell: str) -> str:
    """A model text value as a table cell: literal pipes re-escaped (the schema rule), newlines
    flattened so one row stays one line."""
    return cell.replace("|", r"\|").replace("\n", " ").strip()


def _extra_str(v: object) -> str:
    """An `extra` value as display text: a string passes through; any other JSON value (the model
    accepts them in `extra`) renders as compact JSON."""
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)


def _row(cells: list[str]) -> str:
    return "| " + " | ".join(_esc(c) for c in cells) + " |"


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    sep = "|" + "|".join("---" for _ in headers) + "|"
    return [_row(headers), sep] + [_row(r) for r in rows]


def _source_line(source: str) -> str:
    """A card SOURCE line from the stored href: labelled with the file's basename (its line anchor
    stripped — leaving it in would mislabel `path:line` as `basename:line` instead of `basename`)."""
    label = strip_anchor(source).rsplit("/", 1)[-1] or source
    return f"SOURCE: [{label}]({source})"


def _anchor_link(href: str | None) -> str:
    """A bare `path:line` anchor (components[].entry_point, deps[].where_configured, edges[].where,
    entry_points[].source) as a markdown-link table cell, labelled with its basename — so the
    generated view stays clickable even though the model itself stores these bare, like
    `Entity.source`."""
    if not href:
        return ""
    label = strip_anchor(href).rsplit("/", 1)[-1] or href
    return f"[{label}]({href})"


def _files_str(paths: list[str]) -> str:
    return " · ".join(paths)


_URL_REF = re.compile(r"^[a-z][a-z0-9+.-]*://", re.I)


def _bare_local_file(href: str | None) -> str | None:
    """A bare repo-relative FILE path from a source/anchor href, or None for empty / off-repo /
    directory refs (a directory or URL is not a single openable file). Line anchors are stripped, so
    the result matches the file-browser tree keys."""
    if not href or _URL_REF.match(href):
        return None
    p = strip_anchor(href).strip().strip("/")
    return p if p and not href.rstrip().endswith("/") else None


def _component_files(c: Component) -> list[str]:
    """A component's owned files as bare repo-relative paths — the canonical `source` file first,
    then the rest of `files`, deduped. This is the list the code-viewer switcher pages through."""
    out: list[str] = []
    for f in ([_bare_local_file(c.source)] + [_bare_local_file(f) for f in c.files]):
        if f and f not in out:
            out.append(f)
    return out


def _evidence_str(items: list[EvidenceItem]) -> str:
    """`evidence` as a table cell: one clickable anchor + its why per citation, `·`-separated.
    A blank `why` (allowed for a test suite whose dir name speaks for itself) drops the ` — `."""
    return " · ".join(f"{_anchor_link(ev.file)} — {ev.why}" if ev.why.strip() else _anchor_link(ev.file)
                      for ev in items)


def _resolve_targets(row: TestRow, elems: Mapping[str, object], nodes: Mapping[str, object]) -> list[TestTarget]:
    """A test row's `targets` ids → `{id, name, node}`, resolved server-side (no prose parsing). `name`
    is the defined element's name (falls back to the id when unresolved); `node` is the id when it is a
    drawn diagram node — the viewer makes that clickable to locate the element — else None."""
    out: list[TestTarget] = []
    for tid in row.targets:
        out.append({"id": tid, "name": _element_label(elems.get(tid), tid), "node": tid if tid in nodes else None})
    return out


def _element_label(el: object, fallback: str) -> str:
    """A defined element's human name for display — `name` (most elements), `term` (glossary),
    or `title` (a happy-path step) — falling back to the id when the element is unknown."""
    return str(getattr(el, "name", None) or getattr(el, "term", None)
               or getattr(el, "title", None) or fallback)


def _targets_label(row: TestRow, elems: dict[str, object]) -> str:
    """A test row's targets as a Markdown-view cell: the resolved element names, prefixed by the
    row's optional grouping `label`."""
    joined = ", ".join(_element_label(elems.get(t), t) for t in row.targets)
    if row.label and joined:
        return f"{row.label} ({joined})"
    return row.label or joined


def _relation_item(r) -> str:
    parts = [r.verb]
    if r.src_card and r.dst_card:
        parts.append(f"{r.src_card}→{r.dst_card}")
    parts.append(r.target)
    if r.display:
        parts.append(r.display)
    if r.keyed_by:
        # a storage key, shown with the «key» marker (comma-joined — never `·`, the relation
        # separator); mirrors the canvas arrow label so the text view reads the same.
        parts.append("«key» " + ", ".join(r.keyed_by))
    if r.how:
        parts.append("{" + r.how + "}")
    return " ".join(parts)


def _component_headers(m: ProjectModel) -> tuple[list[str], bool, list[str]]:
    """T1's column set: the canonical six, plus Conf./Files/Evidence when any component states one,
    plus the union of authored extra columns (sorted — deterministic)."""
    with_conf = any(c.confidence for c in m.components)
    extra = sorted({k for c in m.components for k in c.extra})
    headers = ["ID", "Component", "Subsystem", "Purpose", "Entry point", "Depends on"]
    if with_conf:
        headers.append("Conf.")
    if any(c.files for c in m.components):
        headers.append("Files")
    if any(c.evidence for c in m.components):
        headers.append("Evidence")
    if any(c.runs_in for c in m.components):
        headers.append("Runs in")
    return headers + extra, with_conf, extra


def _dep_headers(m: ProjectModel) -> tuple[list[str], bool, list[str]]:
    linked = any(d.deployment_linked for d in m.deps)
    extra = sorted({k for d in m.deps for k in d.extra})
    headers = ["ID", "Name", "Kind", "Bucket", "Type", "Used for", "Where configured", "Conf."]
    if linked:
        headers.append("Deployment-linked")
    if any(d.package for d in m.deps):
        headers.append("Package")
    if any(d.alternative for d in m.deps):
        headers.append("Alternative")
    if any(d.evidence for d in m.deps):
        headers.append("Evidence")
    return headers + extra, linked, extra


def model_to_markdown(m: ProjectModel) -> str:
    """The canonical markdown view. Sections render in the template's order; an empty section is
    omitted (a small map without subsystems reads exactly like any other small map)."""
    out: list[str] = [f"# {m.title} — Codebase Analysis" if m.title else "# Codebase Analysis", ""]
    out += [_GENERATED_NOTICE, ""]
    out += ["> Built with the **coyodex** method. Behavioral layer first (Goal → Glossary → Roles →",
            "> Use cases → Happy Path), then the structural machine (Components → Entry points /",
            "> Model / Deps → Flows + Edges), joined at **use case ↔ flow**.",
            "> The committed source of truth is `project-map.json` (JSON); this file is a generated",
            "> view. IDs, cross-references, and confidence tags are validated by",
            "> `coyodex validate project-map.json`."]
    pin = []
    if m.commit:
        pin.append(f"**Commit:** `{m.commit}`")
    if m.committed:
        pin.append(f"**Committed:** `{m.committed}`")
    if m.built:
        pin.append(f"**Built:** `{m.built}`")
    if pin:
        out.append("> " + " · ".join(pin))
    out.append("")

    def section(title: str, body: list[str]) -> None:
        out.extend(["---", "", f"## {title}", ""] + body + [""])

    if m.goal:
        section("T0 — Goal (the anchor)", [m.goal])
    if m.glossary:
        section("Glossary — the ubiquitous language",
                _table(["Term", "Meaning", "Defined / used in"],
                       [[f"**{g.term}**", g.meaning, _anchor_link(g.source)] for g in m.glossary]))
    if m.roles:
        section("Roles (actors)",
                _table(["Role", "Kind", "What they want", "Use cases they drive"],
                       [[f"**{r.name}**", r.kind, r.wants, r.drives] for r in m.roles]))
    if m.use_cases:
        rn = {r.id: r.name for r in m.roles}  # render actors as role NAMES, resolved from their ids
        section("Use cases",
                _table(["ID", "Use case", "Actor", "Trigger → Outcome"],
                       [[f"**{u.id}**", u.name, ", ".join(rn.get(a, a) for a in u.actors),
                         u.trigger_outcome] for u in m.use_cases]))
    if m.happy_path:
        body = ["The happy-path ordering of use cases. Each step IS a use case (its `*(UCn)*` tag",
                "names it); the step's detail lives in that use case's T6 flow. An optional `why:`",
                "line records the prerequisite that fixes the step's position.", ""]
        for hp in m.happy_path:
            tag = f" *({hp.uc})*" if hp.uc else ""
            body.append(f"**{hp.id} — {hp.title}**{tag}")
            if hp.why:
                body.append(f"why: {hp.why}")
        section("Happy Path — the spine (an ordered walk through the use cases)", body)
    if m.subsystems:
        section("Subsystems (S) — the container altitude",
                _table(["ID", "Subsystem", "Purpose", "Parent", "Source", "Conf."],
                       [[f"**{s.id}**", s.name, s.purpose, s.parent or "", s.source or "",
                         s.confidence] for s in m.subsystems]))
    if m.components:
        headers, with_conf, extra = _component_headers(m)
        rows = []
        for c in m.components:
            row = [f"**{c.id}**", c.name, c.subsystem or "", c.purpose, _anchor_link(c.entry_point),
                   c.depends_on]
            if with_conf:
                row.append(c.confidence)
            if "Files" in headers:
                row.append(_files_str(c.files))
            if "Evidence" in headers:
                row.append(_evidence_str(c.evidence))
            if "Runs in" in headers:
                row.append(", ".join(c.runs_in))
            row += [_extra_str(c.extra.get(k, "")) for k in extra]
            rows.append(row)
        section("T1 — Components", _table(headers, rows))
    if m.deps:
        headers, linked, extra = _dep_headers(m)
        rows = []
        for d in m.deps:
            row = [f"**{d.id}**", d.name, d.kind or "", d.bucket, d.type, d.used_for,
                   _anchor_link(d.where_configured), d.confidence]
            if linked:
                row.append("yes" if d.deployment_linked else "")
            if "Package" in headers:
                row.append(d.package)
            if "Alternative" in headers:
                row.append(d.alternative)
            if "Evidence" in headers:
                row.append(_evidence_str(d.evidence))
            row += [_extra_str(d.extra.get(k, "")) for k in extra]
            rows.append(row)
        section("T2 — External dependencies", _table(headers, rows))
    if m.run_commands:
        section("T3 — How to run / build / test",
                _table(["Action", "Command", "Source"],
                       [[r.action, r.command, r.source] for r in m.run_commands]))
    if m.entry_points:
        section("T4 — Entry points",
                _table(["Kind", "Trigger", "Code entity", "Component"],
                       [[e.kind, e.trigger, _anchor_link(e.source), e.component]
                        for e in m.entry_points]))
    if m.subdomains:
        section("Subdomains (SD) — bounded contexts of the domain model",
                _table(["ID", "Subdomain", "Purpose", "Parent", "Source", "Conf."],
                       [[f"**{s.id}**", s.name, s.purpose, s.parent or "", s.source or "",
                         s.confidence] for s in m.subdomains]))
    if m.entities:
        body: list[str] = []
        for e in m.entities:
            store = f" *({e.store})*" if e.store else ""
            body.append(f"**{e.id} — {e.name}**{store}")
            if e.subdomain:
                body.append(f"SUBDOMAIN: {e.subdomain}")
            if e.meaning:
                body.append(f"MEANING: {e.meaning}")
            if e.fields:
                body.append("FIELDS: " + " · ".join(
                    " ".join([f"{f.name}:{f.type}"] + f.markers).rstrip() for f in e.fields))
            if e.relations:
                body.append("RELATIONS: " + " · ".join(_relation_item(r) for r in e.relations))
            if e.source:
                body.append(_source_line(e.source))
            body.append("")
        section("T5 — Domain model (domain cards)", body[:-1] if body else body)
    if m.non_entity_types:
        section("Non-entity types (plumbing, deliberately unmodelled)",
                _table(["Type", "Source", "Why"],
                       [[t.name, t.source or "", t.why] for t in m.non_entity_types]))
    if m.flows or m.subflows:
        rn = {r.id: r.name for r in m.roles}  # an actor step carries a role id → show the role NAME
        sfn = {sf.id: sf.name for sf in m.subflows}

        def _ep(x: str) -> str:
            return rn.get(x, x) if grammar.is_role_id(x) else x

        def _step_line(st: FlowStep) -> str:  # ONE step-line writer, shared by flows and sub-flows
            line = f"{st.n}. {_ep(st.src)} → {_ep(st.dst)}"
            if st.phrase:
                line += f" : {st.phrase}"
            if st.subflow:  # a reference step: the included run, named inline
                line += f" {'⟨' if st.phrase else ': ⟨'}runs {st.subflow} — {sfn.get(st.subflow, st.subflow)}⟩"
            if st.where:  # the step's own call site (THE location) — rendered as a code link
                line += f" @ {_anchor_link(st.where)}"
            if st.note:
                line += f" · {st.note}"
            return line

        body = []
        for f in m.flows:
            body.append(f"**{f.uc} — {f.title}**")
            body.extend(_step_line(st) for st in f.steps)
            body.append("")
        if m.flows:
            section("T6 — Use-case flows", body[:-1] if body else body)
        if m.subflows:
            body = []
            for sf in m.subflows:
                body.append(f"**{sf.id} — {sf.name}**")
                body.extend(_step_line(st) for st in sf.steps)
                body.append("")
            section("T6b — Sub-flows (shared step sequences, referenced by the flows above)",
                    body[:-1] if body else body)
    if m.deployment or m.observability or m.security or m.config:
        body = []
        if m.deployment:
            body += ["### Deployment & topology", ""] + _table(
                ["Unit", "Runs on", "Exposed as", "Config source"],
                [[r.unit, r.runs_on, r.exposed_as, r.config_source] for r in m.deployment]) + [""]
        if m.observability:
            body += ["### Observability", ""] + _table(
                ["Signal", "Where emitted", "Where viewed", "Alerts"],
                [[r.signal, r.where_emitted, r.where_viewed, r.alerts] for r in m.observability]) + [""]
        if m.security:
            body += ["### Security & auth", ""] + _table(
                ["Surface", "Who can reach", "Auth check", "Risk note"],
                [[r.surface, r.who, r.source, r.risk] for r in m.security]) + [""]
        if m.config:
            body += ["### Config & environments", ""] + _table(
                ["Key", "Purpose", "Default", "Per-env / secret?"],
                [[r.key, r.purpose, r.default, r.per_env] for r in m.config]) + [""]
        section("Operational dimensions — the standard core four", body[:-1])
    if m.edges:
        section("Relationships — backbone edge list",
                _table(["From", "Verb", "To", "Why", "Where (example)"],
                       [[e.src, e.verb, e.dst, e.why or "", _anchor_link(e.where)] for e in m.edges]))
    if m.tests or m.tests_note:
        body = []
        if m.tests_note:
            body += [f"> **Tests run for this table?** {m.tests_note}", ""]
        if m.tests:
            elems = all_elements(m)
            body += _table(["Target", "Tested?", "Test(s)", "Gap / risk", "Confidence"],
                           [[_targets_label(t, elems), t.tested, _evidence_str(t.tests), t.gap, t.confidence]
                            for t in m.tests])
        section("Test completeness — gaps against the map", body)
    for ex in m.extras:
        section(ex.heading, [ex.body] if ex.body else [])
    out += ["---", "",
            "*Generated with coyodex from `project-map.json` — the committed source of truth. "
            "Do not edit this file; regenerate it with `coyodex render`.*", ""]
    return "\n".join(out)


# ── graph view (the HTML viewer's input) ─────────────────────────────────────────────────────────

def _first_href(*cells: str | None) -> str | None:
    for c in cells:
        if c:
            hit = LINK.search(c)
            if hit:
                return hit.group(1)
    return None


def _node(el, kind: str, name: str, file: str | None, fields: dict[str, str],
          parent: str | None) -> Node:
    clean = {k: v for k, v in fields.items() if v}
    return Node(id=el.id, kind=kind, name=name or el.id, file=file, line=_line_of(file),
                fields=clean, parent=parent)


def model_to_graph(m: ProjectModel) -> GraphDict:
    """The model as the viewer's GraphDict, the shape `gen_viewer.build_view_bundle` consumes. A
    component's drill file prefers its canonical `source` and falls back to its `entry_point`,
    then a link found in its free-text fields."""
    nodes: dict[str, Node] = {}
    subsystem_names = {s.id: s.name for s in m.subsystems}
    subdomain_names = {sd.id: sd.name for sd in m.subdomains}
    role_names = {r.id: r.name for r in m.roles}  # role ids → display names (the frontend sees names)
    for u in m.use_cases:
        actor_names = ", ".join(role_names.get(a, a) for a in u.actors)
        nodes[u.id] = _node(u, "usecase", u.name, _first_href(u.trigger_outcome),
                            {"Use case": u.name, "Actor": actor_names,
                             "Trigger → Outcome": u.trigger_outcome}, None)
    for s in m.subsystems:
        parent_name = subsystem_names.get(s.parent, s.parent) if s.parent else ""
        nodes[s.id] = _node(s, "subsystem", s.name, s.source,
                            {"Subsystem": s.name, "Purpose": s.purpose, "Parent": parent_name},
                            s.parent)
    # T4 entry points grouped by the component they name — surfaced as each component's "Triggered by"
    # list in the info pane (the standalone table also lives on the System tab). Each flat entry point
    # also carries `index` = its position within its component's list, so the viewer's search hits and
    # System-tab component links can select the exact entry point in that component's pane.
    eps_by_comp: dict[str, list[dict[str, str]]] = {}
    flat_entry_points: list[dict[str, object]] = []
    for ep in m.entry_points:
        # Activation ("self" = runs with no caller, "external" = something asks): the authored value
        # wins; when absent, derive it from the free-text `kind` — mirrors classify_dep, so old maps
        # (and any untagged entry) still classify without a rebuild.
        activation = grammar.effective_activation(ep.activation, ep.kind)
        ep_dict: dict[str, object] = asdict(ep)
        ep_dict["activation"] = activation
        if ep.component:
            ep_dict["index"] = len(eps_by_comp.setdefault(ep.component, []))
            eps_by_comp[ep.component].append(
                {"kind": ep.kind, "trigger": ep.trigger, "source": ep.source,
                 "activation": activation})
        flat_entry_points.append(ep_dict)
    for c in m.components:
        subsystem_name = subsystem_names.get(c.subsystem, c.subsystem) if c.subsystem else ""
        fields = {"Component": c.name, "Subsystem": subsystem_name, "Purpose": c.purpose,
                  "Entry point": c.entry_point or "",
                  **({"Runs in": ", ".join(c.runs_in)} if c.runs_in else {}),
                  **{k: _extra_str(v) for k, v in c.extra.items()}}
        # `source` is the v2 canonical home; `entry_point` (also bare) is the next best single
        # location; only then fall back to hunting a markdown link in the free-text cells.
        href = c.source or c.entry_point or _first_href(c.purpose, c.depends_on)
        node = _node(c, "component", c.name, href, fields, c.subsystem)
        node.files = _component_files(c)
        node.entry_points = eps_by_comp.get(c.id, [])
        node.runs_in = list(c.runs_in)
        nodes[c.id] = node
    for d in m.deps:
        dep_kind = grammar.classify_dep(d.kind or "", d.type)
        bucket = grammar.resolve_bucket(dep_kind in grammar.DEP_KINDS_FOLDED, d.bucket, d.type, d.used_for)
        fields = {"Name": d.name, "Kind": d.kind or "", "Bucket": bucket, "Type": d.type,
                  "Used for": d.used_for, "Package": d.package,
                  **{k: _extra_str(v) for k, v in d.extra.items()}}
        node = _node(d, "dep", d.name, d.where_configured or _first_href(d.used_for), fields, None)
        node.dep_kind = dep_kind
        nodes[d.id] = node
    for sd in m.subdomains:
        parent_name = subdomain_names.get(sd.parent, sd.parent) if sd.parent else ""
        nodes[sd.id] = _node(sd, "subdomain", sd.name, sd.source,
                             {"Subdomain": sd.name, "Purpose": sd.purpose,
                              "Parent": parent_name}, sd.parent)
    for e in m.entities:
        meta: dict[str, str] = {}
        if e.meaning:
            meta["Meaning"] = e.meaning
        if e.store:
            meta["Stored"] = e.store
        node = Node(id=e.id, kind="entity", name=e.name, file=e.source, line=_line_of(e.source),
                    fields=meta, parent=e.subdomain,
                    attrs=[{"name": f.name, "type": f.type, "markers": " ".join(f.markers)}
                           for f in e.fields])
        ent_file = _bare_local_file(e.source)
        node.files = [ent_file] if ent_file else []
        nodes[e.id] = node

    edges: list[GraphEdge] = []
    seen: set[tuple[str, str, str]] = set()
    for e in m.edges:
        key = (e.src, e.verb, e.dst)
        if key in seen:
            continue
        seen.add(key)
        edges.append(GraphEdge(e.src, e.verb, e.dst, e.why or None, e.where or None))
    for ent in m.entities:
        for r in ent.relations:
            edges.append(GraphEdge(ent.id, r.verb, r.target, None, None,
                                   kind=grammar.REL_KIND.get(r.verb.lower(), "association"),
                                   src_card=r.src_card, dst_card=r.dst_card, how=r.how,
                                   keyed_by=r.keyed_by))
    # Resolve which real field backs each domain relation (drives the arrow label + panel line) —
    # the same second pass the v1 parser ran once all entity nodes existed.
    backing = {e.id: [(f.name, f.type, grammar.fk_targets(f.markers)) for f in e.fields]
               for e in m.entities}
    for ge in edges:
        if ge.kind and ge.kind != "inheritance" and ge.src in backing and ge.dst in backing:
            ge.fk_fields, ge.fk_side = grammar.resolve_backing(
                ge.src, ge.dst, backing[ge.src], backing[ge.dst])

    def _endpoint(x: str) -> str:  # an actor step carries a role id → show the role NAME
        return role_names.get(x, x) if grammar.is_role_id(x) else x

    def _graph_steps(steps: list[FlowStep]) -> list[grammar.FlowStep]:  # shared: flows + sub-flows
        return [grammar.FlowStep(n=st.n, src=_endpoint(st.src), dst=_endpoint(st.dst),
                                 src_is_id=grammar.is_step_id(st.src),
                                 dst_is_id=grammar.is_step_id(st.dst),
                                 phrase=st.phrase, note=st.note, where=st.where,
                                 subflow=st.subflow, ok=True)
                for st in steps]
    flows = [grammar.Flow(uc=f.uc, title=f.title, line_no=0, steps=_graph_steps(f.steps))
             for f in m.flows]
    subflows = [{"id": sf.id, "name": sf.name, "steps": [asdict(s) for s in _graph_steps(sf.steps)]}
                for sf in m.subflows]

    _ensure_default_subsystem(nodes, m.title or None)

    # A group's files = the union of its members' files (subsystems roll up their components, subdomains
    # their entities), recursively through nested groups — so drilling a subsystem's code viewer or
    # highlighting its footprint spans everything it contains. Run after the default-subsystem inject so
    # a synthesized group also rolls up its (now reparented) members. Membership is single-source on the
    # child.
    children_by_parent: dict[str, list[str]] = {}
    for nid, n in nodes.items():
        if n.parent:
            children_by_parent.setdefault(n.parent, []).append(nid)

    def _group_files(gid: str, seen: set[str]) -> list[str]:
        out: list[str] = []
        for cid in children_by_parent.get(gid, []):
            if cid in seen:
                continue
            seen.add(cid)
            child = nodes[cid]
            contrib = _group_files(cid, seen) if child.kind in ("subsystem", "subdomain") else child.files
            for f in contrib:
                if f not in out:
                    out.append(f)
        return out

    for nid, n in nodes.items():
        if n.kind in ("subsystem", "subdomain"):
            n.files = _group_files(nid, set())
    return {
        "commit": m.commit,
        "committed": m.committed,
        "built": m.built,
        "format": m.format or None,
        "title": m.title or None,
        "goal": m.goal or None,
        "nodes": {nid: asdict(n) for nid, n in nodes.items()},
        "edges": [asdict(e) for e in edges],
        "happy_path": [asdict(GraphHappyStep(id=g.id, title=g.title, uc=g.uc, why=g.why or ""))
               for g in m.happy_path],
        "flows": [asdict(f) for f in flows],
        "subflows": subflows,
        "roles": [{"name": r.name, "wants": r.wants, "kind": _role_kind(r.name, r.kind)}
                  for r in m.roles],
        "glossary": [{"term": g.term, "meaning": g.meaning, "source": g.source or ""}
                     for g in m.glossary],
        # ── reference collections (System / Tests tabs) — carried straight from the model ──
        "run_commands": [asdict(r) for r in m.run_commands],
        "entry_points": flat_entry_points,
        "non_entity_types": [asdict(t) for t in m.non_entity_types],
        "deployment": [asdict(r) for r in m.deployment],
        "environments": list(m.environments),
        "observability": [asdict(r) for r in m.observability],
        "security": [asdict(r) for r in m.security],
        "config": [asdict(r) for r in m.config],
        "tests_note": m.tests_note,
        # Rows carry SERVER-RESOLVED targets ({id, name, node}) so the Tests tab renders element
        # names + locate-links with no client-side id parsing; `tests` cites suites as {file, why}.
        "tests": [{
            "targets": _resolve_targets(r, all_elements(m), nodes),
            "label": r.label,
            "tested": r.tested,
            "tests": [asdict(ev) for ev in r.tests],
            "gap": r.gap,
            "confidence": r.confidence,
        } for r in m.tests],
        "extras": [asdict(x) for x in m.extras],
    }
