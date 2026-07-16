"""`coyodex lint-fragment` — the per-fragment self-check a harvest/trace sub-agent runs BEFORE it
returns its fragment.

Today nothing checks a fragment until the LEAD assembles all of them and patches the errors by
guessing, serially. This moves the fix into the agent's own context (where it has the knowledge) and
in parallel: schema, anchor format, `extra`-key conventions, and — with `--repo` — that every anchor's
file actually exists (so a wrong repo-root prefix or a stale line is caught at the source, not by the
lead's `validate`). Reports every finding it can in one pass. Stdlib-only (the cli.py firewall).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from coyodex.assemble import load_fragment
from coyodex.model import ID_SHAPE, ModelError, ProjectModel, all_elements
from coyodex.validate_model import (
    _check_activations,
    _check_anchor_format,
    _check_edges,
    _check_extra_conventions,
    _check_flows,
    _granularity_warnings,
    _referenced_ids,
    check_anchor_existence_model,
    check_domain_relations,
    check_entity_sources_model,
)

# id-SHAPED but unknown-prefix tokens ('SEC1') can never resolve — catchable per-fragment, unlike a
# full undefined-reference check (which needs the whole map, or the --ids universe below).
_ID_LIKE = re.compile(r"^[A-Z]+\d+$")


def _check_reference_shapes(m: ProjectModel) -> list[str]:
    """Reference tokens that LOOK like ids but use a prefix outside the id vocabulary — the
    'tests target SEC1' class: fragment lint used to pass them, and they died only at the lead's
    final validate. A prefix that isn't in the vocabulary can never resolve, so it's a fragment bug."""
    problems: list[str] = []
    for i, tr in enumerate(m.tests):
        for t in tr.targets:
            if _ID_LIKE.match(t) and not ID_SHAPE.match(t):
                problems.append(f"tests[{i}] target '{t}': unknown id prefix — a target must be a "
                                "defined element id (UC/HP/S/SD/SF/C/D/E/R + digits)")
    return problems


def lint_unknown_references(m: ProjectModel, known_ids: set[str]) -> list[str]:
    """With `--ids` (the lead's legend or the assembled map), every cross-reference in the fragment
    must resolve to the fragment's own definitions or the known universe — so an INVENTED id (the
    'tests target C112' class: plausible-looking, defined nowhere) dies in the authoring agent's
    turn instead of at the lead's final validate."""
    defined = set(all_elements(m)) | {g.id for g in m.happy_path} | known_ids
    unresolved = sorted(r for r in _referenced_ids(m) - defined)
    if unresolved:
        return [f"references ids defined neither in this fragment nor in --ids: {', '.join(unresolved)}"]
    return []


def lint_fragment_problems(m: ProjectModel, repo_root: Path | None) -> list[str]:
    """Every non-schema problem in one (partial) fragment: anchor format + `extra`-key conventions +
    the domain-relation rules (`keyed_by` misuse, verb alias, cardinality, dup) + the per-edge rules
    (missing/contradictory `where`, empty verb, intra-fragment dup), plus — when a repo root is given
    — that each anchor / entity source actually exists. This is the shift-left: an authoring agent
    catches its own `keyed_by`/edge mistakes in-context instead of the lead reconciling them a phase
    later at `validate`. Edge-level *warnings* (e.g. `no_call_site` + `where` together) are surfaced as
    lint problems here — at authoring time they are worth fixing before returning the fragment."""
    problems: list[str] = list(_check_anchor_format(m))
    problems += _check_activations(m)  # row-local vocabulary check — an invalid `activation` is a
    # fragment bug (a truthy near-miss would silently reroute the row through the kind heuristic)
    extra_problems, _extra_warnings = _check_extra_conventions(m)
    problems += extra_problems
    rel_problems, _rel_warnings = check_domain_relations(m.entities)
    problems += rel_problems
    edge_problems, edge_warnings = _check_edges(m)
    problems += edge_problems + edge_warnings
    # Flow rules (missing step `where`, duplicate step n, missing phrase/endpoint) fail in the trace
    # agent's own turn, not a phase later at the lead's `validate`. Safe on a partial fragment: the
    # actor-id check self-disables when the fragment defines no roles. Warnings promoted, like edges'.
    flow_problems, flow_warnings = _check_flows(m)
    problems += flow_problems + flow_warnings
    problems += _check_reference_shapes(m)
    if repo_root is not None:
        roots = [repo_root.resolve()]
        problems += check_anchor_existence_model(m, roots)
        problems += check_entity_sources_model(m, roots)
    return problems


def lint_fragment_warnings(m: ProjectModel) -> list[str]:
    """Advisory (non-blocking) findings for one fragment — the domain-relation *warnings* (the
    field-less-association nudge, the by-name-FK hint) and the use-case *granularity* signals
    (flow-length band, fused-goal name smell, shared-run duplication). These are HEURISTIC /
    judgment-shaped, so unlike `lint_fragment_problems` they must NOT fail the lint — the authoring
    agent sees them and decides (a long flow may be the lead's call, not the fragment's bug). Kept
    separate from the blocking problems so the fatal/advisory split is explicit.
    The use-case/Happy-Path COMPLETENESS family (`_completeness_warnings`) is deliberately NOT
    here: it relates T4 ↔ flows ↔ HP across the whole map, and a fragment holds only one slice
    (a T4 harvest fragment has no flows; a trace fragment has no entry points) — per-fragment the
    signal is vacuous or a guaranteed false positive, so it runs in `validate` only."""
    _problems, warnings = check_domain_relations(m.entities)
    return warnings + _granularity_warnings(m)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "-h" in argv or "--help" in argv or not argv:
        print("usage: coyodex lint-fragment [--repo <root>] [--ids <legend-or-map>] <fragment.json>...\n\n"
              "Self-check a build fragment BEFORE returning it: schema, anchor format, `extra`-key\n"
              "conventions, (with --repo) that every anchor's file exists, and (with --ids) that every\n"
              "cross-referenced id is defined in the fragment or the given id universe — pass the\n"
              "lead's legend (_legend.md) or the assembled project-map.json, so an INVENTED id dies\n"
              "here instead of at the lead's final validate. Reports all findings and exits non-zero\n"
              "on any, so an agent fixes its own rows in context instead of the lead hand-patching\n"
              "them after assembly.")
        return 0 if ("-h" in argv or "--help" in argv) else 2
    repo_root: Path | None = None
    known_ids: set[str] | None = None
    frags: list[Path] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--repo":
            i += 1
            if i >= len(argv):
                print("ERROR: --repo needs a directory", file=sys.stderr)
                return 2
            repo_root = Path(argv[i])
        elif a == "--ids":
            i += 1
            if i >= len(argv) or not Path(argv[i]).exists():
                print("ERROR: --ids needs an existing legend/map file", file=sys.stderr)
                return 2
            # any format works: the universe is every id-shaped token in the file (a markdown legend,
            # the assembled map, or a plain id list all read the same way)
            known_ids = {t for t in re.findall(r"\b[A-Z]+\d+\b",
                                               Path(argv[i]).read_text(encoding="utf-8"))
                         if ID_SHAPE.match(t)}
        elif a.startswith("-"):
            print(f"ERROR: unknown option '{a}'", file=sys.stderr)
            return 2
        else:
            frags.append(Path(a))
        i += 1
    if not frags:
        print("ERROR: no fragment given", file=sys.stderr)
        return 2
    clean = True
    for p in frags:
        if not p.exists():
            print(f"ERROR: {p} not found", file=sys.stderr)
            clean = False
            continue
        try:
            m = load_fragment(p.read_text(encoding="utf-8"), p.name)
        except ModelError as e:
            print(f"{p.name}: SCHEMA — {e}", file=sys.stderr)
            clean = False
            continue
        problems = lint_fragment_problems(m, repo_root)
        if known_ids is not None:
            problems += lint_unknown_references(m, known_ids)
        if problems:
            clean = False
            for pr in problems:
                print(f"{p.name}: {pr}", file=sys.stderr)
        else:
            print(f"{p.name}: OK")
        # advisory warnings never fail the lint — heuristic nudges the agent can act on or ignore
        for w in lint_fragment_warnings(m):
            print(f"{p.name}: warning: {w}", file=sys.stderr)
    if not clean:
        print("LINT FAILED: fix the rows above before returning this fragment. "
              "(`warning:` lines are advisory heuristics — they do not fail the lint.)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
