#!/usr/bin/env python3
"""Generated views of the schema-v2 model: model → markdown, and model → graph (the viewer's input).

The markdown view is the READABLE, COMMITTED rendering of `project-map.json` (canonical section
order, template-shaped tables, deterministic output) — never hand-edited; `coyodex validate` warns
when the committed copy is stale. The graph view feeds the existing HTML viewer
(`gen_viewer.write_html`) unchanged: it reproduces exactly the `GraphDict` the schema-v1 parser
built from the equivalent markdown, so the interactive diagram is identical either way.

Stdlib-only. Both functions are pure (same model → same bytes).
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict

from coyodex import schema_v1
from coyodex.model import Component, Dep, Entity, Group, ProjectModel, UseCase
from coyodex.viewer.build_graph import (
    LINK,
    Edge as GraphEdge,
    GPStep as GraphGPStep,
    GraphDict,
    Node,
    _ensure_default_subsystem,
    _line_of,
    _role_kind,
)

# ── markdown view ────────────────────────────────────────────────────────────────────────────────

_GENERATED_NOTICE = (
    "<!-- GENERATED VIEW — do not edit. The source of truth is project-map.json; regenerate this\n"
    "     file with `coyodex render project-map.json project-map.md`. -->")


def _esc(cell: str) -> str:
    """A model text value as a table cell: literal pipes re-escaped (the schema-v1 rule), newlines
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
    """A card SOURCE line from the stored href: labelled with the file's basename."""
    label = source.split("#", 1)[0].rsplit("/", 1)[-1] or source
    return f"SOURCE: [{label}]({source})"


def _relation_item(r) -> str:
    parts = [r.verb]
    if r.src_card and r.dst_card:
        parts.append(f"{r.src_card}→{r.dst_card}")
    parts.append(r.target)
    if r.display:
        parts.append(r.display)
    if r.how:
        parts.append("{" + r.how + "}")
    return " ".join(parts)


def _component_headers(m: ProjectModel) -> tuple[list[str], bool, list[str]]:
    """T1's column set: the canonical six, plus Conf. when any component states one, plus the union
    of authored extra columns (sorted — deterministic)."""
    with_conf = any(c.confidence for c in m.components)
    extra = sorted({k for c in m.components for k in c.extra})
    headers = ["ID", "Component", "Subsystem", "Purpose", "Entry point", "Depends on"]
    if with_conf:
        headers.append("Conf.")
    return headers + extra, with_conf, extra


def _dep_headers(m: ProjectModel) -> tuple[list[str], bool, list[str]]:
    linked = any(d.deployment_linked for d in m.deps)
    extra = sorted({k for d in m.deps for k in d.extra})
    headers = ["ID", "Name", "Kind", "Type", "Used for", "Where configured", "Conf."]
    if linked:
        headers.append("Deployment-linked")
    return headers + extra, linked, extra


def model_to_markdown(m: ProjectModel) -> str:
    """The canonical markdown view. Sections render in the template's order; an empty section is
    omitted (a small map without subsystems reads exactly like a v1 small map)."""
    out: list[str] = [f"# {m.title} — Codebase Analysis" if m.title else "# Codebase Analysis", ""]
    out += [_GENERATED_NOTICE, ""]
    out += ["> Built with the **coyodex** method. Behavioral layer first (Goal → Glossary → Roles →",
            "> Use cases → Golden Path), then the structural machine (Components → Entry points /",
            "> Model / Deps → Flows + Edges), joined at **use case ↔ flow**.",
            "> **Schema v2** (JSON source): the committed source of truth is `project-map.json`;",
            "> this file is a generated view. IDs, cross-references, and confidence tags follow",
            "> schema v1's contract; validated by `coyodex validate project-map.json`."]
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
                       [[f"**{g.term}**", g.meaning, g.where] for g in m.glossary]))
    if m.roles:
        section("Roles (actors)",
                _table(["Role", "Kind", "What they want", "Use cases they drive"],
                       [[f"**{r.name}**", r.kind, r.wants, r.drives] for r in m.roles]))
    if m.use_cases:
        section("Use cases",
                _table(["ID", "Use case", "Actor", "Trigger → Outcome"],
                       [[f"**{u.id}**", u.name, u.actor, u.trigger_outcome] for u in m.use_cases]))
    if m.golden_path:
        body = ["The happy-path ordering of use cases. Each step IS a use case (its `*(UCn)*` tag",
                "names it); the step's detail lives in that use case's T6 flow. An optional `why:`",
                "line records the prerequisite that fixes the step's position.", ""]
        for gp in m.golden_path:
            tag = f" *({gp.uc})*" if gp.uc else ""
            body.append(f"**{gp.id} — {gp.title}**{tag}")
            if gp.why:
                body.append(f"why: {gp.why}")
        section("Golden Path — the spine (an ordered walk through the use cases)", body)
    if m.subsystems:
        section("Subsystems (S) — the container altitude",
                _table(["ID", "Subsystem", "Purpose", "Parent", "Anchor", "Conf."],
                       [[f"**{s.id}**", s.name, s.purpose, s.parent or "", s.anchor or "",
                         s.confidence] for s in m.subsystems]))
    if m.components:
        headers, with_conf, extra = _component_headers(m)
        rows = []
        for c in m.components:
            row = [f"**{c.id}**", c.name, c.subsystem or "", c.purpose, c.entry_point or "",
                   c.depends_on]
            if with_conf:
                row.append(c.confidence)
            row += [_extra_str(c.extra.get(k, "")) for k in extra]
            rows.append(row)
        section("T1 — Components", _table(headers, rows))
    if m.deps:
        headers, linked, extra = _dep_headers(m)
        rows = []
        for d in m.deps:
            row = [f"**{d.id}**", d.name, d.kind or "", d.type, d.used_for, d.where_configured,
                   d.confidence]
            if linked:
                row.append("yes" if d.deployment_linked else "")
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
                       [[e.kind, e.trigger, e.entity, e.component] for e in m.entry_points]))
    if m.subdomains:
        section("Subdomains (SD) — bounded contexts of the domain model",
                _table(["ID", "Subdomain", "Purpose", "Parent", "Anchor", "Conf."],
                       [[f"**{s.id}**", s.name, s.purpose, s.parent or "", s.anchor or "",
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
    if m.flows:
        body = []
        for f in m.flows:
            body.append(f"**{f.uc} — {f.title}**")
            for st in f.steps:
                line = f"{st.n}. {st.src} → {st.dst}"
                if st.phrase:
                    line += f" : {st.phrase}"
                if st.note:
                    line += f" · {st.note}"
                body.append(line)
            body.append("")
        section("T6 — Use-case flows", body[:-1] if body else body)
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
                [[r.surface, r.who, r.check, r.risk] for r in m.security]) + [""]
        if m.config:
            body += ["### Config & environments", ""] + _table(
                ["Key", "Purpose", "Default", "Per-env / secret?"],
                [[r.key, r.purpose, r.default, r.per_env] for r in m.config]) + [""]
        section("Operational dimensions — the standard core four", body[:-1])
    if m.edges:
        section("Relationships — backbone edge list",
                _table(["From", "Verb", "To", "Why", "Where"],
                       [[e.src, e.verb, e.dst, e.why or "", e.where or ""] for e in m.edges]))
    if m.tests or m.tests_note:
        body = []
        if m.tests_note:
            body += [f"> **Tests run for this table?** {m.tests_note}", ""]
        if m.tests:
            body += _table(["Target", "Tested?", "Test(s)", "Gap / risk", "Confidence"],
                           [[t.target, t.tested, t.tests, t.gap, t.confidence] for t in m.tests])
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
    """The model as the viewer's GraphDict — the same shape `build_graph.build` produced from the
    equivalent schema-v1 markdown, so `gen_viewer.write_html` renders it unchanged. A component's
    drill file prefers its v2 canonical `anchor` and falls back to the entry-point link (the v1
    first-row-link heuristic, so converted maps render identically)."""
    nodes: dict[str, Node] = {}
    for u in m.use_cases:
        nodes[u.id] = _node(u, "usecase", u.name, _first_href(u.trigger_outcome),
                            {"Use case": u.name, "Actor": u.actor,
                             "Trigger → Outcome": u.trigger_outcome}, None)
    for s in m.subsystems:
        nodes[s.id] = _node(s, "subsystem", s.name, _first_href(s.anchor),
                            {"Subsystem": s.name, "Purpose": s.purpose, "Parent": s.parent or "",
                             "Anchor": s.anchor or "", "Conf.": s.confidence}, s.parent)
    for c in m.components:
        fields = {"Component": c.name, "Subsystem": c.subsystem or "", "Purpose": c.purpose,
                  "Entry point": c.entry_point or "", "Depends on": c.depends_on,
                  "Conf.": c.confidence,
                  **{k: _extra_str(v) for k, v in c.extra.items()}}
        # `anchor` is a bare `path#Lnnn` (the v2 canonical home); the fallback is the v1 heuristic —
        # the first md link across the row's cells (usually the entry point).
        href = c.anchor or _first_href(c.entry_point, c.purpose, c.depends_on)
        nodes[c.id] = _node(c, "component", c.name, href, fields, c.subsystem)
    for d in m.deps:
        fields = {"Name": d.name, "Kind": d.kind or "", "Type": d.type, "Used for": d.used_for,
                  "Where configured": d.where_configured, "Conf.": d.confidence,
                  **{k: _extra_str(v) for k, v in d.extra.items()}}
        node = _node(d, "dep", d.name, _first_href(d.where_configured, d.used_for), fields, None)
        node.dep_kind = schema_v1.classify_dep(d.kind or "", d.type)
        nodes[d.id] = node
    for sd in m.subdomains:
        nodes[sd.id] = _node(sd, "subdomain", sd.name, _first_href(sd.anchor),
                             {"Subdomain": sd.name, "Purpose": sd.purpose,
                              "Parent": sd.parent or "", "Anchor": sd.anchor or "",
                              "Conf.": sd.confidence}, sd.parent)
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
        nodes[e.id] = node

    edges: list[GraphEdge] = []
    seen: set[tuple[str, str, str]] = set()
    for e in m.edges:
        key = (e.src, e.verb, e.dst)
        if key in seen:
            continue
        seen.add(key)
        where = _first_href(e.where) or (e.where or None)
        edges.append(GraphEdge(e.src, e.verb, e.dst, e.why or None, where))
    for ent in m.entities:
        for r in ent.relations:
            edges.append(GraphEdge(ent.id, r.verb, r.target, None, None,
                                   kind=schema_v1.REL_KIND.get(r.verb.lower(), "association"),
                                   src_card=r.src_card, dst_card=r.dst_card, how=r.how))
    # Resolve which real field backs each domain relation (drives the arrow label + panel line) —
    # the same second pass the v1 parser ran once all entity nodes existed.
    backing = {e.id: [(f.name, f.type, schema_v1.fk_targets(f.markers)) for f in e.fields]
               for e in m.entities}
    for ge in edges:
        if ge.kind and ge.kind != "inheritance" and ge.src in backing and ge.dst in backing:
            ge.fk_field, ge.fk_side = schema_v1.resolve_backing(
                ge.src, ge.dst, backing[ge.src], backing[ge.dst])

    flows = [schema_v1.Flow(
        uc=f.uc, title=f.title, line_no=0,
        steps=[schema_v1.FlowStep(n=st.n, src=st.src, dst=st.dst,
                                  src_is_id=schema_v1.is_step_id(st.src),
                                  dst_is_id=schema_v1.is_step_id(st.dst),
                                  phrase=st.phrase, note=st.note, ok=True)
               for st in f.steps]) for f in m.flows]

    _ensure_default_subsystem(nodes, m.title or None)
    return {
        "commit": m.commit,
        "committed": m.committed,
        "title": m.title or None,
        "goal": m.goal or None,
        "nodes": {nid: asdict(n) for nid, n in nodes.items()},
        "edges": [asdict(e) for e in edges],
        "gp": [asdict(GraphGPStep(id=g.id, title=g.title, uc=g.uc, why=g.why or ""))
               for g in m.golden_path],
        "flows": [asdict(f) for f in flows],
        "roles": [{"name": r.name, "wants": r.wants, "kind": _role_kind(r.name, r.kind)}
                  for r in m.roles],
    }
