"""`coyodex lint-fragment` — the per-fragment self-check a harvest/trace sub-agent runs BEFORE it
returns its fragment.

Today nothing checks a fragment until the LEAD assembles all of them and patches the errors by
guessing, serially. This moves the fix into the agent's own context (where it has the knowledge) and
in parallel: schema, anchor format, `extra`-key conventions, and — with `--repo` — that every anchor's
file actually exists (so a wrong repo-root prefix or a stale line is caught at the source, not by the
lead's `validate`). Reports every finding it can in one pass. Stdlib-only (the cli.py firewall).
"""
from __future__ import annotations

import sys
from pathlib import Path

from coyodex.assemble import load_fragment
from coyodex.model import ModelError, ProjectModel
from coyodex.validate_model import (
    _check_anchor_format,
    _check_edges,
    _check_extra_conventions,
    _check_flows,
    check_anchor_existence_model,
    check_domain_relations,
    check_entity_sources_model,
)


def lint_fragment_problems(m: ProjectModel, repo_root: Path | None) -> list[str]:
    """Every non-schema problem in one (partial) fragment: anchor format + `extra`-key conventions +
    the domain-relation rules (`keyed_by` misuse, verb alias, cardinality, dup) + the per-edge rules
    (missing/contradictory `where`, empty verb, intra-fragment dup), plus — when a repo root is given
    — that each anchor / entity source actually exists. This is the shift-left: an authoring agent
    catches its own `keyed_by`/edge mistakes in-context instead of the lead reconciling them a phase
    later at `validate`. Edge-level *warnings* (e.g. `no_call_site` + `where` together) are surfaced as
    lint problems here — at authoring time they are worth fixing before returning the fragment."""
    problems: list[str] = list(_check_anchor_format(m))
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
    if repo_root is not None:
        roots = [repo_root.resolve()]
        problems += check_anchor_existence_model(m, roots)
        problems += check_entity_sources_model(m, roots)
    return problems


def lint_fragment_warnings(m: ProjectModel) -> list[str]:
    """Advisory (non-blocking) findings for one fragment — the domain-relation *warnings*: the
    field-less-association nudge and the heuristic "this field-less relation looks like a by-name FK,
    mark `FK→…`" hint. These are HEURISTIC (they read prose), so unlike `lint_fragment_problems` they
    must NOT fail the lint — the authoring agent sees them and decides. Kept separate from the blocking
    problems so the fatal/advisory split is explicit."""
    _problems, warnings = check_domain_relations(m.entities)
    return warnings


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "-h" in argv or "--help" in argv or not argv:
        print("usage: coyodex lint-fragment [--repo <root>] <fragment.json>...\n\n"
              "Self-check a build fragment BEFORE returning it: schema, anchor format, `extra`-key\n"
              "conventions, and (with --repo) that every anchor's file exists. Reports all findings and\n"
              "exits non-zero on any, so an agent fixes its own rows in context instead of the lead\n"
              "hand-patching them after assembly.")
        return 0 if ("-h" in argv or "--help" in argv) else 2
    repo_root: Path | None = None
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
