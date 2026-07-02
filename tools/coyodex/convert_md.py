#!/usr/bin/env python3
"""One-time converter: a schema-v1 markdown map → the schema-v2 JSON model (method/model.md).

Built ON the existing shared parse (schema_v1 + the viewer's grammar) — the model is what that
parse already yields, made explicit — plus capture of the sections the graph parse never needed
(Glossary, T3, T4, the operational tables, test completeness), so the generated markdown view
loses no content the tools or a reader use.

The converter is for maps that ALREADY VALIDATE under schema v1: malformed rows the v1 pipeline
silently skipped (an edge row without both ids, a not-`from → to` flow step, a malformed RELATIONS
item) are skipped here too, each reported as a conversion warning — never silently.

Driven by `coyodex convert <project-map.md> [--out <dir>]`, which writes the canonical
project-map.json plus the regenerated md + HTML views next to it. Stdlib-only.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from coyodex import schema_v1
from coyodex.model import (
    ConfigRow,
    Component,
    Dep,
    DeploymentRow,
    Edge,
    Entity,
    EntityField,
    EntityRelation,
    EntryPoint,
    ExtraSection,
    Flow,
    FlowStep,
    GlossaryRow,
    GoldenStep,
    Group,
    NonEntityType,
    ObservabilityRow,
    ProjectModel,
    Role,
    RunRow,
    SecurityRow,
    TestRow,
    UseCase,
)
from coyodex.viewer.build_graph import parse_goal, parse_gp

_COMMIT = re.compile(r"\*\*Commit:\*\*\s*`([^`]+)`")
_COMMITTED = re.compile(r"\*\*Committed:\*\*\s*`([^`]+)`")
_BUILT = re.compile(r"\*\*Built:\*\*\s*`([^`]+)`")
_TESTS_NOTE = re.compile(r"^>\s*\*\*Tests run for this table\?\*\*\s*(.*)$")

# Section headings the canonical view regenerates — an unmatched `##` section is preserved
# verbatim in `extras` instead (minus any table already parsed into the model).
_RECOGNIZED = re.compile(
    r"^##\s+(T\d\b|Glossary\b|Roles\b|Use cases\b|Golden Path\b|Subsystems\b|Subdomains\b"
    r"|Operational\b|Relationships\b|Test completeness\b)")


@dataclass
class ConvertResult:
    model: ProjectModel
    warnings: list[str]


def _strip_bold(s: str) -> str:
    return re.sub(r"\*+", "", s).strip()


def _first_id(cell: str) -> str | None:
    m = schema_v1.ID_TOKEN.search(cell)
    return m.group(0) if m else None


def _hidx(headers: list[str], *needles: str, starts: bool = False) -> int | None:
    """Index of the first header matching any needle (substring, or prefix when `starts`)."""
    for i, h in enumerate(headers):
        for n in needles:
            if (h.startswith(n) if starts else n in h):
                return i
    return None


def _cell(cells: list[str], idx: int | None) -> str:
    return cells[idx].strip() if idx is not None and 0 <= idx < len(cells) else ""


def _opt(s: str) -> str | None:
    return s if s else None


def _classify(headers: list[str], rows: list[list[str]]) -> str | None:
    """The table's kind, by headers first, else by the id prefix its rows define. None = unrecognized."""
    hl = [h.lower() for h in headers]
    if hl[:3] == ["from", "verb", "to"]:
        return "edges"
    if hl and hl[0] == "role":
        return "roles"
    if hl and hl[0] == "term":
        return "glossary"
    if hl[:3] == ["action", "command", "source"]:
        return "run"
    if hl and hl[0] == "surface" and "auth check" in hl:
        return "security"
    if hl and hl[0] == "kind" and "component" in hl:
        return "entry_points"
    if hl and hl[0] == "unit":
        return "deployment"
    if hl and hl[0] == "signal":
        return "observability"
    if hl and hl[0] == "key" and ("purpose" in hl or any("per-env" in h for h in hl)):
        return "config"
    if hl and hl[0] == "target" and any("tested" in h for h in hl):
        return "tests"
    # Definition tables — classify by the id prefix of the first defining row.
    for cells in rows:
        if not cells:
            continue
        m = schema_v1.DEF_ID_CELL.search(cells[0])
        if not m:
            continue
        eid = m.group(1)
        pre = re.match(r"[A-Z]+", eid).group(0)  # type: ignore[union-attr]
        return {"UC": "use_cases", "S": "subsystems", "SD": "subdomains",
                "C": "components", "D": "deps"}.get(pre)
    return None


def _membership(cells: list[str], headers: list[str], child_id: str,
                warnings: list[str]) -> str | None:
    ids = schema_v1.membership_ids(child_id, cells, headers)
    if len(ids) > 1:
        warnings.append(f"{child_id}: multiple parents in its membership cell "
                        f"({', '.join(ids)}) — kept the first ({ids[0]})")
    return ids[0] if ids else None


def _extract_display(raw: str, target: str) -> str:
    """The display text an authored RELATIONS item carries after its target id."""
    m = re.search(rf"\b{target}\b", raw)
    return raw[m.end():].strip() if m else ""


def convert_text(raw: str) -> ConvertResult:
    """Parse a schema-v1 map into the schema-v2 model. Raises ValueError on an unterminated code
    fence (the parse would silently truncate — fix the map first, exactly as `validate` demands)."""
    fence = schema_v1.unterminated_fence_line(raw)
    if fence is not None:
        raise ValueError(f"unterminated code fence at line {fence} — everything after it would be "
                         "silently dropped from the conversion; close the fence and re-run")
    text = schema_v1.strip_fences(raw)
    lines = text.splitlines()
    warnings: list[str] = []
    m = ProjectModel()

    title_m = re.search(r"^#\s+(.+?)\s*$", text, re.M)
    title = title_m.group(1).strip() if title_m else ""
    if " — " in title:
        title = title.split(" — ")[0].strip()
    m.title = title
    m.goal = parse_goal(text) or ""
    for pat, attr in ((_COMMIT, "commit"), (_COMMITTED, "committed"), (_BUILT, "built")):
        hit = pat.search(text)
        if hit:
            setattr(m, attr, hit.group(1))

    for gp in parse_gp(lines):
        m.golden_path.append(GoldenStep(id=gp.id, title=gp.title, uc=gp.uc, why=_opt(gp.why)))
        if gp.uc is None:
            warnings.append(f"{gp.id}: Golden Path step has no *(UCn)* tag (kept; validate flags it)")

    for card in schema_v1.iter_domain_cards(lines):
        relations: list[EntityRelation] = []
        for r in card.relations:
            if not r.ok:
                warnings.append(f"{card.id}: malformed RELATIONS item skipped: '{r.raw}'")
                continue
            relations.append(EntityRelation(
                verb=r.verb, target=r.target, src_card=r.src_card, dst_card=r.dst_card,
                display=_extract_display(r.raw, r.target), how=r.how))
        m.entities.append(Entity(
            id=card.id, name=card.name, store=card.store, meaning=card.meaning,
            subdomain=card.subdomain, source=card.source,
            fields=[EntityField(f.name, f.type, list(f.markers)) for f in card.fields],
            relations=relations))
        if not card.heading_ok:
            warnings.append(f"{card.id}: malformed card heading (name/store fell back to the id)")

    for flow in schema_v1.iter_flows(lines):
        steps: list[FlowStep] = []
        for st in flow.steps:
            if not st.ok:
                warnings.append(f"{flow.uc} flow step {st.n}: not a `from → to` interaction — skipped")
                continue
            steps.append(FlowStep(n=st.n, src=st.src, dst=st.dst, phrase=st.phrase, note=st.note))
        m.flows.append(Flow(uc=flow.uc, title=flow.title, steps=steps))

    consumed: set[int] = set()  # line indices of tables parsed into the model (for `extras`)
    for start, block in schema_v1.iter_pipe_runs(lines):
        if len(block) < 2:
            continue  # a detached row — validate's problem, preserved for extras
        headers = schema_v1.split_cells(block[0])
        hl = [h.lower() for h in headers]
        rows = [schema_v1.split_cells(r) for r in block[1:] if not schema_v1.is_separator_row(r)]
        kind = _classify(headers, rows)
        if kind is None:
            continue  # unrecognized table — preserved verbatim in extras
        consumed.update(range(start, start + len(block)))
        if kind == "edges":
            wi, yi = _hidx(hl, "where"), _hidx(hl, "why")
            for cells in rows:
                src, dst = _first_id(_cell(cells, 0)), _first_id(_cell(cells, 2))
                if not (src and dst):
                    warnings.append(f"edge row skipped (no id on both ends): "
                                    f"'{' | '.join(cells)[:80]}'")
                    continue
                m.edges.append(Edge(src=src, verb=_cell(cells, 1), dst=dst,
                                    why=_opt(_cell(cells, yi)), where=_opt(_cell(cells, wi))))
        elif kind == "roles":
            ki, wi, di = _hidx(hl, "kind"), _hidx(hl, "want"), _hidx(hl, "drive", "use case")
            for cells in rows:
                name = _strip_bold(_cell(cells, 0))
                if name:
                    m.roles.append(Role(name=name, kind=_cell(cells, ki),
                                        wants=_cell(cells, wi), drives=_cell(cells, di)))
        elif kind == "glossary":
            mi, di = _hidx(hl, "meaning"), _hidx(hl, "defined", "used in", "where")
            for cells in rows:
                term = _strip_bold(_cell(cells, 0))
                if term:
                    m.glossary.append(GlossaryRow(term=term, meaning=_cell(cells, mi),
                                                  where=_cell(cells, di)))
        elif kind == "use_cases":
            ni = _hidx(hl, "use case", starts=True)
            ai, ti = _hidx(hl, "actor"), _hidx(hl, "trigger")
            for cells in rows:
                dm = schema_v1.DEF_ID_CELL.search(_cell(cells, 0))
                if dm:
                    m.use_cases.append(UseCase(id=dm.group(1), name=_cell(cells, ni),
                                               actor=_cell(cells, ai),
                                               trigger_outcome=_cell(cells, ti)))
        elif kind in ("subsystems", "subdomains"):
            ni = _hidx(hl, "subsystem" if kind == "subsystems" else "subdomain")
            pi, ci = _hidx(hl, "purpose"), _hidx(hl, "conf", starts=True)
            anc = _hidx(hl, "anchor")
            out = m.subsystems if kind == "subsystems" else m.subdomains
            for cells in rows:
                dm = schema_v1.DEF_ID_CELL.search(_cell(cells, 0))
                if dm:
                    out.append(Group(id=dm.group(1), name=_cell(cells, ni),
                                     purpose=_cell(cells, pi),
                                     parent=_membership(cells, hl, dm.group(1), warnings),
                                     anchor=_opt(_cell(cells, anc)), confidence=_cell(cells, ci)))
        elif kind == "components":
            known = {"id", "component", "subsystem", "purpose", "entry point", "depends on", "conf",
                     "conf."}
            ni, pi = _hidx(hl, "component"), _hidx(hl, "purpose")
            ei, di, ci = (_hidx(hl, "entry point"), _hidx(hl, "depends on"),
                          _hidx(hl, "conf", starts=True))
            for cells in rows:
                dm = schema_v1.DEF_ID_CELL.search(_cell(cells, 0))
                if not dm:
                    continue
                extra: dict[str, object] = {
                    headers[i]: cells[i].strip() for i in range(1, len(cells))
                    if i < len(headers) and hl[i] not in known and cells[i].strip()}
                m.components.append(Component(
                    id=dm.group(1), name=_cell(cells, ni),
                    subsystem=_membership(cells, hl, dm.group(1), warnings),
                    purpose=_cell(cells, pi), entry_point=_opt(_cell(cells, ei)),
                    depends_on=_cell(cells, di), anchor=None, confidence=_cell(cells, ci),
                    extra=extra))
        elif kind == "deps":
            known = {"id", "name", "kind", "type", "used for", "where configured", "conf", "conf."}
            ni, ki, ti = _hidx(hl, "name"), _hidx(hl, "kind"), _hidx(hl, "type")
            ui, wi, ci = (_hidx(hl, "used for"), _hidx(hl, "where configured"),
                          _hidx(hl, "conf", starts=True))
            for cells in rows:
                dm = schema_v1.DEF_ID_CELL.search(_cell(cells, 0))
                if not dm:
                    continue
                extra: dict[str, object] = {
                    headers[i]: cells[i].strip() for i in range(1, len(cells))
                    if i < len(headers) and hl[i] not in known and cells[i].strip()}
                m.deps.append(Dep(
                    id=dm.group(1), name=_cell(cells, ni), kind=_opt(_cell(cells, ki)),
                    type=_cell(cells, ti), used_for=_cell(cells, ui),
                    where_configured=_cell(cells, wi), confidence=_cell(cells, ci), extra=extra))
        elif kind == "run":
            for cells in rows:
                if _cell(cells, 0):
                    m.run_commands.append(RunRow(action=_cell(cells, 0), command=_cell(cells, 1),
                                                 source=_cell(cells, 2)))
        elif kind == "entry_points":
            ti, ei, ci = _hidx(hl, "trigger"), _hidx(hl, "code entity", "entity"), _hidx(hl, "component")
            for cells in rows:
                if not any(c.strip() for c in cells):
                    continue
                comp_cell = _cell(cells, ci)
                m.entry_points.append(EntryPoint(kind=_cell(cells, 0), trigger=_cell(cells, ti),
                                                 entity=_cell(cells, ei),
                                                 component=_first_id(comp_cell) or comp_cell))
        elif kind == "security":
            wi, ci, ri = _hidx(hl, "who"), _hidx(hl, "auth check"), _hidx(hl, "risk")
            for cells in rows:
                if _cell(cells, 0):
                    m.security.append(SecurityRow(surface=_cell(cells, 0), who=_cell(cells, wi),
                                                  check=_cell(cells, ci), risk=_cell(cells, ri)))
        elif kind == "deployment":
            ri, ei, ci = _hidx(hl, "runs on"), _hidx(hl, "exposed"), _hidx(hl, "config")
            for cells in rows:
                if _cell(cells, 0):
                    m.deployment.append(DeploymentRow(unit=_cell(cells, 0), runs_on=_cell(cells, ri),
                                                      exposed_as=_cell(cells, ei),
                                                      config_source=_cell(cells, ci)))
        elif kind == "observability":
            ei, vi, ai = _hidx(hl, "emitted"), _hidx(hl, "viewed"), _hidx(hl, "alert")
            for cells in rows:
                if _cell(cells, 0):
                    m.observability.append(ObservabilityRow(
                        signal=_cell(cells, 0), where_emitted=_cell(cells, ei),
                        where_viewed=_cell(cells, vi), alerts=_cell(cells, ai)))
        elif kind == "config":
            pi, di, ei = _hidx(hl, "purpose"), _hidx(hl, "default"), _hidx(hl, "per-env", "secret")
            for cells in rows:
                if _cell(cells, 0):
                    m.config.append(ConfigRow(key=_cell(cells, 0), purpose=_cell(cells, pi),
                                              default=_cell(cells, di), per_env=_cell(cells, ei)))
        elif kind == "tests":
            ti, si, gi, ci = (_hidx(hl, "tested"), _hidx(hl, "test(s)", "tests"),
                              _hidx(hl, "gap"), _hidx(hl, "conf", starts=True))
            for cells in rows:
                if _cell(cells, 0):
                    m.tests.append(TestRow(target=_cell(cells, 0), tested=_cell(cells, ti),
                                           tests=_cell(cells, si), gap=_cell(cells, gi),
                                           confidence=_cell(cells, ci)))

    note = next((t.group(1).strip() for line in lines if (t := _TESTS_NOTE.match(line.strip()))), "")
    m.tests_note = note

    m.extras = _collect_extras(lines, consumed)
    for ex in m.extras:
        warnings.append(f"unrecognized section preserved verbatim in extras: '{ex.heading}'")
    return ConvertResult(model=m, warnings=warnings)


def _collect_extras(lines: list[str], consumed: set[int]) -> list[ExtraSection]:
    """Unrecognized `##` sections, preserved verbatim (minus tables already parsed into the model
    and HTML comments) so a converted map loses no authored content the view should keep showing."""
    out: list[ExtraSection] = []
    i, n = 0, len(lines)
    while i < n:
        s = lines[i].strip()
        if not s.startswith("## ") or _RECOGNIZED.match(s):
            i += 1
            continue
        heading = s[3:].strip()
        j = i + 1
        body: list[str] = []
        while j < n and not lines[j].strip().startswith("## "):
            if j not in consumed and not lines[j].strip().startswith("<!--"):
                body.append(lines[j])
            j += 1
        body_text = "\n".join(body).strip()
        if body_text or heading:
            out.append(ExtraSection(heading=heading, body=body_text))
        i = j
    return out


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "-h" in argv or "--help" in argv:
        print("usage: coyodex convert <project-map.md> [--out <dir>]\n\n"
              "One-time migration of a schema-v1 markdown map to the schema-v2 JSON model.\n"
              "Writes <dir>/project-map.json (the new committed source) plus the regenerated\n"
              "markdown and HTML views next to it (default <dir> = the map's own directory —\n"
              "the in-place case REPLACES the hand-authored project-map.md with the generated\n"
              "view; the old text stays in git history). Review, then commit json+md+html.")
        return 0
    out_dir: Path | None = None
    positional: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--out":
            i += 1
            if i >= len(argv):
                print("ERROR: --out needs a directory", file=sys.stderr)
                return 2
            out_dir = Path(argv[i])
        elif a.startswith("-"):
            print(f"ERROR: unknown option '{a}'", file=sys.stderr)
            return 2
        else:
            positional.append(a)
        i += 1
    src = Path(positional[0] if positional else ".coyodex/project-map.md")
    if not src.exists():
        print(f"ERROR: {src} not found", file=sys.stderr)
        return 1
    raw = src.read_text(encoding="utf-8")
    # Refuse an INVALID v1 map: the v1 parse silently drops what its validator flags (a malformed
    # `S12a` id, a split table), so converting it would bake the silent loss into the new source.
    from coyodex.schema_v1 import strip_fences, unterminated_fence_line
    from coyodex.validate_analysis import validate_map
    if unterminated_fence_line(raw) is None:
        problems, _ = validate_map(strip_fences(raw), src)
        if problems:
            print("ERROR: the markdown map does not validate under schema v1 — fix it first "
                  "(`coyodex validate <map.md>`), then convert. Problems:", file=sys.stderr)
            for p in problems:
                print(f"  - {p}", file=sys.stderr)
            return 1
    try:
        result = convert_text(raw)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    # Import here (not at module top) to keep converter importable without the view layer in play
    # during tests; both are stdlib-only, this is only about narrow test seams.
    from coyodex.model import to_canonical_json
    from coyodex.views import model_to_graph, model_to_markdown
    from coyodex.viewer.gen_viewer import write_html

    dest = out_dir if out_dir is not None else src.parent
    dest.mkdir(parents=True, exist_ok=True)
    json_path = dest / "project-map.json"
    json_path.write_text(to_canonical_json(result.model), encoding="utf-8")
    md_path = dest / "project-map.md"
    replaced = md_path.resolve() == src.resolve()
    md_path.write_text(model_to_markdown(result.model), encoding="utf-8")
    html_path = dest / "project-map.html"
    write_html(model_to_graph(result.model), html_path, None)
    for w in result.warnings:
        print(f"WARNING: {w}", file=sys.stderr)
    note = (" (the hand-authored original was replaced by the generated view — the old text stays "
            "in git history)" if replaced else "")
    print(f"Converted {src} -> {json_path}\n"
          f"Views: {md_path} (generated markdown){note}, {html_path} (viewer)\n"
          f"Next: coyodex validate {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
