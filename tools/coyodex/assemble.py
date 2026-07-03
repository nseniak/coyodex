#!/usr/bin/env python3
"""`coyodex assemble` — structured rows → the canonical model (the parallel-build assembler).

Build agents return STRUCTURED ROWS: each harvest/trace agent's output is saved verbatim as a
JSON *fragment* — a partial model holding a subset of the top-level arrays (components, edges,
entities, …) and, in at most one fragment, the header singletons (title / goal / commit /
committed / built). This command validates every fragment against the schema (one bad fragment
fails ALONE, with its file and JSON path named — the whole point of assembling with a tool),
merges them (arrays concatenate in argument order; a duplicate ID across fragments is an ERROR,
never a silent overwrite), and writes the canonical `project-map.json` plus its generated markdown
and HTML views. The LLM never hand-authors the stored format: validity is guaranteed here, by the
serializer.

A fragment is the model document minus the strictness that only the WHOLE map needs: `format` is
optional in a fragment, every top-level field is optional, and cross-fragment references are NOT
resolved here — that is `coyodex validate`'s job on the assembled result (the usual invariant
`validate → audit → render` still runs after assembly). Stdlib-only.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import fields
from pathlib import Path

from coyodex.model import (
    FORMAT,
    ID_ARRAYS,
    ModelError,
    ProjectModel,
    _build,
    to_canonical_json,
)
from coyodex.validate_analysis import strip_anchor

_SINGLETONS = ("title", "goal", "commit", "committed", "built", "tests_note")

_MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_HASH_LINE = re.compile(r"#L(\d+)(?:-L?(\d+))?$")  # retired `#Lnnn` / `#Lnnn-Lmmm` anchor suffix


def _to_colon_line(href: str) -> str:
    """Rewrite a retired `path#Lnnn` / `path#Lnnn-Lmmm` anchor to the canonical `path:line` /
    `path:line-line` — the one line-number syntax the method now mandates (method/model.md's
    'Anchor formats')."""
    m = _HASH_LINE.search(href)
    if not m:
        return href
    start, end = m.groups()
    return href[:m.start()] + (f":{start}-{end}" if end else f":{start}")


def load_fragment(text: str, label: str) -> ProjectModel:
    """A fragment parsed + structurally validated as a partial model. `format` defaults to the
    current one so agents don't have to state it; everything else validates exactly like the map."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ModelError(f"{label}: not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ModelError(f"{label}: top level: expected an object")
    data.setdefault("format", FORMAT)
    if data["format"] != FORMAT:
        raise ModelError(f"{label}: format: expected '{FORMAT}', got {data['format']!r}")
    return _build(data, ProjectModel, label)


def merge_fragments(parts: list[tuple[str, ProjectModel]]) -> tuple[ProjectModel, list[str]]:
    """Merge validated fragments into one model. Returns (model, problems); problems are merge
    conflicts (duplicate IDs across fragments, a singleton stated twice with different values) —
    each names both fragments, so the lead re-pings the right agent instead of hand-fixing JSON."""
    out = ProjectModel()
    problems: list[str] = []
    id_owner: dict[str, str] = {}
    singleton_owner: dict[str, str] = {}
    for label, frag in parts:
        for name in _SINGLETONS:
            val = getattr(frag, name)
            if val in (None, ""):
                continue
            prev = getattr(out, name)
            if prev in (None, ""):
                setattr(out, name, val)
                singleton_owner[name] = label
            elif prev != val:
                problems.append(f"'{name}' stated by both {singleton_owner[name]} and {label} "
                                f"with different values — keep it in ONE header fragment")
        for f in fields(ProjectModel):
            if f.name in _SINGLETONS or f.name == "format":
                continue
            frag_list = getattr(frag, f.name)
            if not isinstance(frag_list, list) or not frag_list:
                continue
            getattr(out, f.name).extend(frag_list)
        for attr in ID_ARRAYS:
            for el in getattr(frag, attr):
                if el.id in id_owner and id_owner[el.id] != label:
                    problems.append(f"duplicate id {el.id}: defined by both {id_owner[el.id]} "
                                    f"and {label} — agents must keep to their pre-allocated ID ranges")
                id_owner.setdefault(el.id, label)
    return out, problems


def normalize_anchors(m: ProjectModel, repo_root: Path | None) -> list[str]:
    """Normalize the anchor-format asymmetry agents most often get wrong (every Phase-2 fragment
    came back md-linked): `components[].anchor` and `entities[].source` must be BARE repo-relative
    refs — an md link is reduced to its href; group anchors (`subsystems`/`subdomains`) must be md
    LINKS — a bare path is wrapped, keeping an authored link's label untouched; a directory anchor
    gets its trailing `/` when `repo_root` (best-effort: the parent of --out) shows it is a
    directory; a retired `path#Lnnn` / `path#Lnnn-Lmmm` line anchor (on any of these fields, plus
    `edges[].where` / `entry_points[].entity` hrefs) is rewritten to the canonical `path:line` /
    `path:line-line`. Returns one note per normalized field, so the fix-up is visible, never silent."""
    notes: list[str] = []

    def bare(cell: str) -> str:
        hit = _MD_LINK.search(cell)
        return _to_colon_line((hit.group(1).strip() if hit else cell.strip()))

    def with_dir_slash(href: str) -> str:
        # `bare()` already colon-normalizes, so a file-like ref no longer carries a `#` — the
        # "already anchored" guard has to recognize the canonical `:line`/`:line-line` suffix instead
        # (shared with the validator's anchor stripping: `strip_anchor` changed something → it had one).
        if repo_root is None or not href or href.endswith("/") or strip_anchor(href) != href:
            return href
        return href + "/" if (repo_root / href).is_dir() else href

    def note(owner: str, field_name: str, fixed: str) -> None:
        notes.append(f"{owner}: {field_name} normalized to '{fixed}'")

    def fix_link(cell: str) -> str | None:
        """`cell` is an md link; return the cell with its href colon-normalized, or None if
        unchanged."""
        hit = _MD_LINK.search(cell)
        if not hit:
            return None
        href = hit.group(1).strip()
        fixed_href = _to_colon_line(href)
        return cell.replace(f"({href})", f"({fixed_href})") if fixed_href != href else None

    for c in m.components:
        if c.anchor:
            fixed = with_dir_slash(bare(c.anchor))
            if fixed != c.anchor:
                note(c.id, "anchor", fixed)
                c.anchor = fixed
        if c.entry_point:
            fixed = fix_link(c.entry_point)
            if fixed is not None:
                note(c.id, "entry_point", fixed)
                c.entry_point = fixed
    for d in m.deps:
        if d.where_configured:
            fixed = fix_link(d.where_configured)
            if fixed is not None:
                note(d.id, "where_configured", fixed)
                d.where_configured = fixed
    for e in m.entities:
        if e.source:
            fixed = bare(e.source)
            if fixed != e.source:
                note(e.id, "source", fixed)
                e.source = fixed
    for g in (*m.subsystems, *m.subdomains):
        if not g.anchor:
            continue
        hit = _MD_LINK.search(g.anchor)
        if hit:  # already a link — only repair a missing directory slash, keep the label
            href = hit.group(1).strip()
            fixed_href = with_dir_slash(href)
            if fixed_href != href:
                fixed = g.anchor.replace(f"({href})", f"({fixed_href})")
                note(g.id, "anchor", fixed)
                g.anchor = fixed
        else:
            href = with_dir_slash(g.anchor.strip())
            label = href.rstrip("/").rsplit("/", 1)[-1] or href
            fixed = f"[{label}]({href})"
            note(g.id, "anchor", fixed)
            g.anchor = fixed
    for edge in m.edges:
        if edge.where:
            fixed = fix_link(edge.where)
            if fixed is not None:
                note(f"{edge.src} → {edge.dst}", "where", fixed)
                edge.where = fixed
    for ep in m.entry_points:
        if ep.entity:
            fixed = fix_link(ep.entity)
            if fixed is not None:
                note(ep.component or ep.kind, "entity", fixed)
                ep.entity = fixed
    return notes


def ensure_fragments_ignored(out_dir: Path) -> bool:
    """Make `<out>/.gitignore` ignore `build-fragments/` (the method's scratch dir for agents'
    fragments) — the tool writes the ignore entry the method promises, so a build in a normal
    checkout never leaves a dirty tree for the eval's pin guard to refuse. Returns True when the
    entry was added (False = already present)."""
    gi = out_dir / ".gitignore"
    line = "build-fragments/"
    if gi.exists():
        content = gi.read_text(encoding="utf-8")
        if line in (ln.strip() for ln in content.splitlines()):
            return False
        sep = "" if (not content or content.endswith("\n")) else "\n"
        gi.write_text(content + sep + line + "\n", encoding="utf-8")
    else:
        gi.write_text(line + "\n", encoding="utf-8")
    return True


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "-h" in argv or "--help" in argv or not argv:
        print("usage: coyodex assemble <fragment.json>... --out <dir>\n\n"
              "Merge build agents' structured-row fragments into the canonical project-map.json\n"
              "(+ the generated markdown and HTML views) in <dir>. Each fragment is a PARTIAL\n"
              "model (any subset of the top-level arrays; one header fragment may carry\n"
              "title/goal/commit). A malformed fragment or a duplicate ID fails loudly with the\n"
              "fragment named. Anchor formats are normalized (a component/entity md-link anchor\n"
              "becomes its bare href; a bare group anchor becomes a link; a directory anchor gets\n"
              "its trailing '/', checked against <dir>'s parent as the repo root; a retired\n"
              "'path#Lnnn' line anchor becomes the canonical 'path:line') — each fix-up is printed.\n"
              "<dir>/.gitignore gets a 'build-fragments/' entry so the scratch dir never\n"
              "dirties the tree. Then run the usual invariant: validate → audit → render.")
        return 0 if ("-h" in argv or "--help" in argv) else 2
    out_dir: Path | None = None
    frags: list[Path] = []
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
            frags.append(Path(a))
        i += 1
    if out_dir is None:
        print("ERROR: --out <dir> is required", file=sys.stderr)
        return 2
    if not frags:
        print("ERROR: no fragments given", file=sys.stderr)
        return 2
    parts: list[tuple[str, ProjectModel]] = []
    bad = False
    for p in frags:
        if not p.exists():
            print(f"ERROR: {p} not found", file=sys.stderr)
            bad = True
            continue
        try:
            parts.append((p.name, load_fragment(p.read_text(encoding="utf-8"), p.name)))
        except ModelError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            bad = True
    if bad:
        print("ASSEMBLY FAILED: fix (or re-request) the fragments above; nothing was written.",
              file=sys.stderr)
        return 1
    model, problems = merge_fragments(parts)
    if problems:
        for pr in problems:
            print(f"ERROR: {pr}", file=sys.stderr)
        print("ASSEMBLY FAILED: merge conflicts above; nothing was written.", file=sys.stderr)
        return 1
    # Best-effort repo root for the directory-slash check: the map dir sits directly under the
    # analyzed repo's root (`--out .coyodex`), so its parent is the root in the normal layout.
    for n in normalize_anchors(model, out_dir.resolve().parent):
        print(f"note: {n}")
    from coyodex.viewer.gen_viewer import write_html
    from coyodex.views import model_to_graph, model_to_markdown

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "project-map.json").write_text(to_canonical_json(model), encoding="utf-8")
    (out_dir / "project-map.md").write_text(model_to_markdown(model), encoding="utf-8")
    write_html(model_to_graph(model), out_dir / "project-map.html", None)
    if ensure_fragments_ignored(out_dir):
        print(f"note: added 'build-fragments/' to {out_dir / '.gitignore'}")
    print(f"Assembled {len(parts)} fragment(s) -> {out_dir / 'project-map.json'} "
          f"(+ generated md/html views)\n"
          f"Next: coyodex validate {out_dir / 'project-map.json'} --check-sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
