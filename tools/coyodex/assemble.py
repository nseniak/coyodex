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
`validate --check-sources → audit → render` still runs after assembly). Stdlib-only.
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

_SINGLETONS = ("title", "goal", "commit", "committed", "built", "tests_note")


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
    _merge_duplicate_deps(out)
    _merge_duplicate_edges(out)  # AFTER dep-merge: re-pointing src/dst can create new exact dups
    return out, problems


def _dep_identity(d) -> tuple[str, str]:
    """A dependency's real identity: its kind + normalized name (or package). The same external dep
    discovered by several harvest agents (different ids) shares this."""
    name = (d.name or d.package or "").strip().lower()
    return ((d.kind or "").strip().lower(), name)


def _merge_duplicate_deps(m: ProjectModel) -> None:
    """Collapse deps that share a real identity (kind + normalized name) into ONE row, and RE-POINT
    every edge from the merged-away id to the survivor. Multiple agents discovering the same dependency
    is CORRECT input (not an error), so slicing harvest by directory no longer duplicates deps. Only an
    exact identity match merges — a differing kind is a different identity, left as two rows (never a
    wrong merge). Deterministic: the first occurrence is the survivor."""
    survivor_of: dict[tuple[str, str], str] = {}
    remap: dict[str, str] = {}
    kept = []
    for d in m.deps:
        ident = _dep_identity(d)
        if not ident[1]:            # no name/package → not identifiable, keep as-is
            kept.append(d)
            continue
        if ident in survivor_of:
            remap[d.id] = survivor_of[ident]
        else:
            survivor_of[ident] = d.id
            kept.append(d)
    if not remap:
        return
    m.deps = kept
    for e in m.edges:               # edges are the only refs into a dep id (C→D)
        e.src = remap.get(e.src, e.src)
        e.dst = remap.get(e.dst, e.dst)


def _merge_duplicate_edges(m: ProjectModel) -> None:
    """Collapse backbone edges that are the SAME relationship at the SAME call site — identical
    `(src, verb, dst, where)` with a CONCRETE `where` — into one, keeping the first (deterministic).
    Parallel trace agents each independently emit the same `C→E`/`enforces` edge; nothing deduped
    them, so the stored map + markdown table carried the redundant rows. Merging on a real anchor is
    SAFE — the exact `file:line` pins the fact, so it is unambiguously one edge; only the `why`
    rationale varies in wording (both describe the same fact), and the backbone keeps one `why` per
    edge (the differing prose belongs in the T6 flow steps).

    A `no_call_site` edge (null `where`) is NEVER merged — with no anchor to disambiguate, a differing
    `why` may be the only signal that two DISTINCT couplings exist (two events on the same C→C pair),
    so those fall through to `validate`'s duplicate-edge warning for a human to reconcile. Likewise an
    edge that shares `(src, verb, dst)` but points at a DIFFERENT anchor is left as-is (which call
    site is the true one — a duplicate once masked a wrong anchor). Mirrors `_merge_duplicate_deps`:
    only an unambiguous identity merges, never a wrong one."""
    seen: set[tuple[str, str, str, str]] = set()
    kept = []
    for e in m.edges:
        if not e.where:                        # no concrete anchor → can't safely disambiguate; keep
            kept.append(e)                     # (validate's duplicate-triple warning surfaces these)
            continue
        key = (e.src, e.verb, e.dst, e.where)
        if key in seen:
            continue
        seen.add(key)
        kept.append(e)
    m.edges = kept


_GITIGNORE_KEEP = "build-fragments/"       # the agents' scratch dir — never committed
# `preindex.json` is a COMMITTED artifact (the viewer's symbol search reads it, pinned to the map's
# commit), so it must NOT be ignored. Strip any stray ignore line (an older build, a hand edit) so it
# can't drift back out of version control. Match the plain name and a root-anchored form.
_GITIGNORE_DROP = {"preindex.json", "/preindex.json"}


def ensure_fragments_ignored(out_dir: Path) -> bool:
    """Normalize `<out>/.gitignore`: ensure `build-fragments/` (the agents' scratch dir) IS ignored so
    a build never dirties the tree, and ensure `preindex.json` is NOT ignored so the committed
    pre-index the viewer relies on stays in version control. Any other lines are left untouched.
    Returns True when the file changed (created, the entry added, or a stray preindex ignore stripped)."""
    gi = out_dir / ".gitignore"
    old_lines = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
    new_lines = [ln for ln in old_lines if ln.strip() not in _GITIGNORE_DROP]
    if _GITIGNORE_KEEP not in (ln.strip() for ln in new_lines):
        new_lines.append(_GITIGNORE_KEEP)
    if new_lines == old_lines:
        return False
    gi.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return True


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "-h" in argv or "--help" in argv or not argv:
        print("usage: coyodex assemble <fragment.json>... --out <dir>\n\n"
              "Merge build agents' structured-row fragments into the canonical project-map.json\n"
              "(+ the generated markdown and HTML views) in <dir>. Each fragment is a PARTIAL\n"
              "model (any subset of the top-level arrays; one header fragment may carry\n"
              "title/goal/commit). A malformed fragment or a duplicate ID fails loudly with the\n"
              "fragment named — nothing is silently fixed up; run `coyodex validate` on the\n"
              "result to catch anything else wrong.\n"
              "<dir>/.gitignore gets a 'build-fragments/' entry so the scratch dir never\n"
              "dirties the tree. Then run the usual invariant: validate --check-sources → audit → render.")
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
    raw_edges = sum(len(fr.edges) for _, fr in parts)  # before merge, to report the dedup
    model, problems = merge_fragments(parts)
    if problems:
        for pr in problems:
            print(f"ERROR: {pr}", file=sys.stderr)
        print("ASSEMBLY FAILED: merge conflicts above; nothing was written.", file=sys.stderr)
        return 1
    collapsed = raw_edges - len(model.edges)  # only _merge_duplicate_edges removes edges (deps re-point)
    if collapsed > 0:
        print(f"note: collapsed {collapsed} duplicate backbone edge(s) (same call site)")
    from coyodex.views import model_to_markdown

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "project-map.json").write_text(to_canonical_json(model), encoding="utf-8")
    (out_dir / "project-map.md").write_text(model_to_markdown(model), encoding="utf-8")
    # The interactive viewer is served live by `coyodex serve` (built on demand from the model), so no
    # HTML file is written here — registering the folder is enough for the server to pick it up.
    from coyodex.viewer.recents import register_project  # registers the project with `coyodex serve` (best-effort)
    register_project(out_dir)
    if ensure_fragments_ignored(out_dir):
        print(f"note: added 'build-fragments/' to {out_dir / '.gitignore'}")
    for note in _unconsumed_fragment_notes(out_dir, frags):
        print(note, file=sys.stderr)
    print(f"Assembled {len(parts)} fragment(s) -> {out_dir / 'project-map.json'} "
          f"(+ generated markdown view)\n"
          f"Next: coyodex validate {out_dir / 'project-map.json'} --check-sources")
    return 0


def _unconsumed_fragment_notes(out_dir: Path, consumed: list[Path]) -> list[str]:
    """Warn about fragments sitting in `<out>/build-fragments/` that were NOT passed to assemble — a
    sub-agent that wrote to the wrong folder (`voice/.coyodex/…`) or a stale file the lead forgot. A
    silently-dropped fragment reads as "assembled everything" when a whole slice is missing."""
    frag_dir = out_dir / "build-fragments"
    if not frag_dir.is_dir():
        return []
    consumed_resolved = {p.resolve() for p in consumed}
    strays = [f for f in sorted(frag_dir.glob("*.json")) if f.resolve() not in consumed_resolved]
    return [f"note: {frag_dir / f.name} is in build-fragments/ but was NOT assembled — a sub-agent may "
            "have written to the wrong path, or it is stale; pass it or delete it." for f in strays]


if __name__ == "__main__":
    raise SystemExit(main())
