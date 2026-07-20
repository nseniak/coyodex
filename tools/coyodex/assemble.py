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

from coyodex import grammar
from coyodex.model import (
    FORMAT,
    ID_ARRAYS,
    ID_SHAPE,
    Edge,
    FlowStep,
    ModelError,
    ProjectModel,
    _build,
    remap_element_ids,
    to_canonical_json,
)
from coyodex.reconcile import (
    ReconcileError,
    apply_reconcile,
    load_reconcile,
    validate_reconcile,
)
from coyodex.validate_model import unbacked_entity_steps

_SINGLETONS = ("title", "goal", "commit", "committed", "built", "tests_note")

# Phase-4 verdicts files ({"grounding": [...]}) sometimes land in build-fragments/ and get caught by
# a `*.json` glob — they are NOT fragments. Recognised so `assemble` skips them with a note instead
# of failing the whole build (the failure a fresh build hit and had to hand-fix mid-run).
_FRAGMENT_KEYS = {f.name for f in fields(ProjectModel)}

# C→E edge verb inferred from the step's LEADING verb. Entity-step phrases are action-first ("upserts
# the membership document", "reads the user record"), so the first verb IS the operation — matching it
# alone avoids the noun traps a substring scan hits ("reads the asset metadata" must not become a WRITE
# because "asset" contains "set"). A write-family verb ESTABLISHES ownership (the 'owning component'
# check reads persists/writes), so anything not clearly a write defaults to `reads` — a derived edge
# never invents ownership (the honest direction: an ownerless entity stays flagged, not falsely owned).
# The verb families live in `grammar` (the one place backbone-verb meaning is decided — DRY); this
# derivation and `grammar.edge_role` read the SAME vocabulary, so a new verb is added once.


def _infer_ce_verb(phrase: str) -> str:
    words = re.findall(r"[a-z]+", (phrase or "").lower())
    lead = words[0] if words else ""
    if lead in grammar.PERSIST_VERBS:
        return "persists"
    if lead in grammar.WRITE_VERBS:
        return "writes"
    if lead in grammar.EMIT_VERBS:
        return "emits"
    if lead in grammar.ENCRYPT_VERBS:
        return "encrypts"
    return "reads"  # a read verb or anything ambiguous → never over-claims ownership


def _is_verdicts_file(text: str) -> bool:
    """A Phase-4 verdicts file ({"grounding": [...]}), not a build fragment — no fragment field is
    present. (A real fragment that merely also carried a stray `grounding` key would still be caught,
    because it WOULD share a fragment key and this returns False.)"""
    try:
        obj = json.loads(text)
    except ValueError:
        return False
    return isinstance(obj, dict) and "grounding" in obj and not (set(obj) & _FRAGMENT_KEYS)


def _derive_entity_edges(m: ProjectModel, stats: dict[str, int]) -> list[str]:
    """Create the C→E backbone edge each unbacked entity flow-step implies. The step already carries
    the evidence (its C and E endpoints + a `where`); at scale a trace agent authors the entity STEP
    but forgets the paired edge (both fresh builds shipped ~a dozen such, leaving entities with no
    'owning component' and no impact reachability). Deriving here is IDEMPOTENT (regenerated from the
    steps on every assemble, so it survives re-assembly — unlike a post-assemble `fix`) and additive
    (only pairs no edge already carries). Verb inferred from the phrase; ambiguous → `reads`, so a
    derived edge never invents ownership. Returns a short `C verb E` log for the assemble note."""
    unbacked = unbacked_entity_steps(m)
    if not unbacked:
        return []
    ownership = {"persists", "writes"}
    chosen: dict[tuple[str, str], tuple[str, FlowStep]] = {}
    for _label, st, c_id, e_id in unbacked:
        verb = _infer_ce_verb(st.phrase)
        prev = chosen.get((c_id, e_id))
        # first step wins, but upgrade to an ownership verb if any step for this pair implies one
        if prev is None or (verb in ownership and prev[0] not in ownership):
            chosen[(c_id, e_id)] = (verb, st)
    for (c_id, e_id), (verb, st) in chosen.items():
        m.edges.append(Edge(src=c_id, verb=verb, dst=e_id,
                            why="derived from entity flow-step",
                            where=st.where, no_call_site=not bool(st.where)))
    stats["entity_edges_derived"] = len(chosen)
    return [f"{c} {v} {e}" for (c, e), (v, _st) in chosen.items()]


def load_fragment(text: str, label: str) -> ProjectModel:
    """A fragment parsed + structurally validated as a partial model. `format` defaults to the
    current one so agents don't have to state it; everything else validates exactly like the map —
    INCLUDING the id-shape/prefix rule (`S1a` in a fragment must die at the authoring agent's own
    `lint-fragment`, not a phase later at the lead's validate — the shift-left this module exists
    for; the rule was previously run only by `load_model`)."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ModelError(f"{label}: not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ModelError(f"{label}: top level: expected an object")
    data.setdefault("format", FORMAT)
    if data["format"] != FORMAT:
        raise ModelError(f"{label}: format: expected '{FORMAT}', got {data['format']!r}")
    m = _build(data, ProjectModel, label)
    for attr, prefix in ID_ARRAYS.items():
        for i, el in enumerate(getattr(m, attr)):
            eid = el.id
            good = bool(ID_SHAPE.match(eid)) and re.match(r"[A-Z]+", eid).group(0) == prefix  # type: ignore[union-attr]
            if not good:
                raise ModelError(f"{label}: $.{attr}[{i}].id: '{eid}' is not a valid {prefix}-id "
                                 f"(a schema id is the prefix + digits only, e.g. {prefix}3)")
    return m


def merge_fragments(parts: list[tuple[str, ProjectModel]],
                    stats: dict[str, int] | None = None) -> tuple[ProjectModel, list[str]]:
    """Merge validated fragments into one model. Returns (model, problems); problems are merge
    conflicts (duplicate IDs across fragments, a singleton stated twice with different values) —
    each names both fragments, so the lead re-pings the right agent instead of hand-fixing JSON.

    Pass a `stats` dict to receive the auto-clean pass counts (actor-endpoint edges stripped,
    duplicate components merged, duplicate edges collapsed) — `main` reports them; test callers that
    omit it are unaffected."""
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
    actor_stripped = _strip_actor_edges(out)          # actors are never backbone endpoints
    comp_merged = _merge_duplicate_components(out)     # same module harvested by two slices → one
    edges_before_dup = len(out.edges)
    _merge_duplicate_edges(out)  # LAST: dep-merge / actor-strip / component re-point can create exact dups
    if stats is not None:
        stats["actor_edges_stripped"] = actor_stripped
        stats["components_merged"] = comp_merged
        stats["duplicate_edges_collapsed"] = edges_before_dup - len(out.edges)
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


def _strip_actor_edges(m: ProjectModel) -> int:
    """Drop backbone edges whose endpoint is an actor (a Role id). The edge list connects
    components / deps / entities ONLY — an actor's participation lives in a T6 flow STEP, never the
    backbone (method.md). A trace agent that emits `R3 → C5` is a PROMPT DEFECT, not correct input
    (unlike the same dep found by two harvest agents), so `main` reports a non-zero count as a
    WARNING for the lead to fix the trace prompt at the source. Returns the number stripped."""
    role_ids = {role.id for role in m.roles}
    if not role_ids:
        return 0
    kept = [e for e in m.edges if e.src not in role_ids and e.dst not in role_ids]
    n = len(m.edges) - len(kept)
    m.edges = kept
    return n


def _component_identity(c) -> tuple[str, str] | None:
    """A component's merge identity: `(normalized FILE source anchor, normalized name)`, or None when
    it can't be safely deduped — no source, a DIRECTORY-anchor source (a shared directory is not
    identity: two different components legitimately live under one dir), or no name. Only a real file
    anchor + matching name means "the same module harvested by two overlapping slices" (the transcript
    case). Deliberately stricter than `_dep_identity`: a component key is far more consequential."""
    src = (c.source or "").strip()
    if not src or src.endswith("/"):        # missing, or a directory anchor → not a safe identity
        return None
    name = (c.name or "").strip().lower()
    if not name:
        return None
    return (src.lower(), name)


def _merge_duplicate_components(m: ProjectModel) -> int:
    """Collapse components that are the SAME module harvested twice by overlapping slices — identical
    normalized `(file source, name)` — into ONE, keeping the first (deterministic), and RE-POINT every
    reference to the merged-away id via `remap_element_ids` (the COMPLETE inbound set — edges, flow/
    sub-flow steps, entry-point owners, test targets, and `[[Cn]]` prose — so nothing is left dangling
    for `validate` to block on). Mirrors `_merge_duplicate_deps`; only an unambiguous file+name
    identity merges (a directory-anchored or nameless component is never merged). Returns the count."""
    survivor_of: dict[tuple[str, str], str] = {}
    remap: dict[str, str] = {}
    kept = []
    for c in m.components:
        ident = _component_identity(c)
        if ident is None:
            kept.append(c)
            continue
        if ident in survivor_of:
            remap[c.id] = survivor_of[ident]
        else:
            survivor_of[ident] = c.id
            kept.append(c)
    if not remap:
        return 0
    m.components = kept
    remap_element_ids(m, remap)
    return len(remap)


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
        print("usage: coyodex assemble <fragment.json>... --out <dir> [--reconcile <file>]\n\n"
              "Merge build agents' structured-row fragments into the canonical project-map.json\n"
              "(+ the generated markdown and HTML views) in <dir>. Each fragment is a PARTIAL\n"
              "model (any subset of the top-level arrays; one header fragment may carry\n"
              "title/goal/commit). A malformed fragment or a duplicate ID fails loudly with the\n"
              "fragment named — nothing is silently fixed up; run `coyodex validate` on the\n"
              "result to catch anything else wrong.\n\n"
              "--reconcile <file>: a declarative reconcile input applied AFTER the merge (and after\n"
              "  entity-edge derivation), BEFORE the write — so a re-assemble always re-applies it.\n"
              "  `set` bulk-assigns subsystem/subdomain/runs_in/bucket; `drop_edges` removes refuted\n"
              "  edges and heals the flow steps that rode them. Keep this file OUTSIDE\n"
              "  build-fragments/ (e.g. .coyodex/reconcile.json) so the fragment glob does not sweep it.\n\n"
              "<dir>/.gitignore gets a 'build-fragments/' entry so the scratch dir never\n"
              "dirties the tree. Then run the usual invariant: validate --check-sources → audit → render.")
        return 0 if ("-h" in argv or "--help" in argv) else 2
    out_dir: Path | None = None
    reconcile_path: Path | None = None
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
        elif a == "--reconcile":
            i += 1
            if i >= len(argv):
                print("ERROR: --reconcile needs a file", file=sys.stderr)
                return 2
            reconcile_path = Path(argv[i])
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
        text = p.read_text(encoding="utf-8")
        try:
            parts.append((p.name, load_fragment(text, p.name)))
        except ModelError as e:
            if _is_verdicts_file(text):
                print(f"note: skipping {p.name} — a Phase-4 verdicts file, not a build fragment "
                      f"(keep verdicts out of build-fragments/ or feed them to `anchor-drift` / "
                      f"`fix apply-drift`, not `assemble`)", file=sys.stderr)
                continue
            print(f"ERROR: {e}", file=sys.stderr)
            bad = True
    if bad:
        print("ASSEMBLY FAILED: fix (or re-request) the fragments above; nothing was written.",
              file=sys.stderr)
        return 1
    stats: dict[str, int] = {}
    model, problems = merge_fragments(parts, stats)
    if problems:
        for pr in problems:
            print(f"ERROR: {pr}", file=sys.stderr)
        print("ASSEMBLY FAILED: merge conflicts above; nothing was written.", file=sys.stderr)
        return 1
    if stats.get("actor_edges_stripped"):
        print(f"WARNING: stripped {stats['actor_edges_stripped']} actor-endpoint edge(s) — edges "
              f"connect components/deps/entities only, never actors. This is a trace-prompt defect: "
              f"fix the prompt so agents put actor participation in flow STEPS, not the backbone.",
              file=sys.stderr)
    if stats.get("components_merged"):
        print(f"note: merged {stats['components_merged']} duplicate component(s) "
              f"(same file harvested by overlapping slices)")
    if stats.get("duplicate_edges_collapsed"):
        print(f"note: collapsed {stats['duplicate_edges_collapsed']} duplicate backbone edge(s) "
              f"(same call site)")
    derived = _derive_entity_edges(model, stats)
    if derived:
        shown = ", ".join(derived[:8]) + (f", +{len(derived) - 8} more" if len(derived) > 8 else "")
        print(f"note: derived {len(derived)} C→E backbone edge(s) from entity flow-steps that had "
              f"none (verb inferred from the step; ambiguous → reads): {shown}")
    # `--reconcile` is applied AFTER `_derive_entity_edges` (B1): a `drop_edges` on a C→E edge must run
    # after the derive, or the derive re-creates the just-dropped edge from its surviving flow step.
    rec_stats: dict[str, object] = {}
    if reconcile_path is not None:
        if not reconcile_path.exists():
            print(f"ERROR: --reconcile {reconcile_path} not found", file=sys.stderr)
            return 1
        try:
            rec = load_reconcile(reconcile_path.read_text(encoding="utf-8"), reconcile_path.name)
        except ReconcileError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            print("ASSEMBLY FAILED: bad reconcile file; nothing was written.", file=sys.stderr)
            return 1
        rec_problems = validate_reconcile(model, rec)
        if rec_problems:
            for pr in rec_problems:
                print(f"ERROR: {pr}", file=sys.stderr)
            print("ASSEMBLY FAILED: reconcile directives above are invalid; nothing was written.",
                  file=sys.stderr)
            return 1
        rec_notes = apply_reconcile(model, rec, rec_stats)
        for note in rec_notes:
            print(note, file=sys.stderr if note.startswith("WARNING") else sys.stdout)
        sc = rec_stats.get("reconcile_set", {})
        set_summary = (", ".join(f"{k}: {v}" for k, v in sc.items() if v)
                       if isinstance(sc, dict) else "") or "nothing"
        print(f"note: reconcile applied — set {{{set_summary}}}; "
              f"drop_edges: {rec_stats.get('reconcile_edges_dropped', 0)} edge(s).")
    elif out_dir is not None and (out_dir / "reconcile.json").exists():
        # S8: a reconcile file is present but was NOT passed — an assemble without it silently reverts
        # every synthesis/trace assignment. Nudge, don't guess (the lead may have meant to omit it).
        print(f"note: {out_dir / 'reconcile.json'} exists but --reconcile was not passed — this "
              f"assemble did NOT apply it, so any subsystem/subdomain/runs_in/bucket/drop it holds is "
              f"absent from the written map. Re-run with `--reconcile {out_dir / 'reconcile.json'}`.",
              file=sys.stderr)
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
          f"(+ generated markdown view)")
    # WS-T2: a self-describing one-line digest of WHAT this assemble did, so a transcript audit (builds
    # alias the CLI) can see the auto-clean + reconcile effects without reverse-engineering a script.
    print(f"  {_assemble_digest(model, stats, rec_stats)}")
    print(f"Next: coyodex validate {out_dir / 'project-map.json'} --check-sources")
    return 0


def _assemble_digest(model: ProjectModel, stats: dict[str, int], rec_stats: dict[str, object]) -> str:
    """One-line, self-describing summary of the assemble: the resulting inventory plus every mutation
    the auto-clean passes and `--reconcile` made (all zero-suppressed) — the WS-T2 transcript trail."""
    inv = {"C": len(model.components), "D": len(model.deps), "E": len(model.entities),
           "edges": len(model.edges), "S": len(model.subsystems), "SD": len(model.subdomains)}
    parts = [f"model: {', '.join(f'{k}:{v}' for k, v in inv.items() if v)}"]
    ops: list[str] = []
    if stats.get("actor_edges_stripped"):
        ops.append(f"actor-edges stripped {stats['actor_edges_stripped']}")
    if stats.get("components_merged"):
        ops.append(f"components merged {stats['components_merged']}")
    if stats.get("duplicate_edges_collapsed"):
        ops.append(f"dup-edges collapsed {stats['duplicate_edges_collapsed']}")
    if stats.get("entity_edges_derived"):
        ops.append(f"C→E edges derived {stats['entity_edges_derived']}")
    sc = rec_stats.get("reconcile_set", {})
    if isinstance(sc, dict) and any(sc.values()):
        ops.append("reconcile set " + "/".join(f"{k}:{v}" for k, v in sc.items() if v))
    if rec_stats.get("reconcile_edges_dropped"):
        ops.append(f"reconcile drop_edges {rec_stats['reconcile_edges_dropped']}")
    parts.append("ops: " + ("; ".join(ops) if ops else "none"))
    return " | ".join(parts)


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
            "have written to the wrong path, or it is stale; pass it, delete it, or move a "
            "superseded raw fragment into build-fragments/raw/ (subdirectories are not scanned)."
            for f in strays]


if __name__ == "__main__":
    raise SystemExit(main())
