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

from coyodex import grammar
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
    roleless_cd_verb_warnings,
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


def _id_prefix(tok: str) -> str:
    """The id's leading letters (its namespace): `UC19`→`UC`, `SD2`→`SD`, `C5`→`C`."""
    mo = re.match(r"[A-Z]+", tok)
    return mo.group(0) if mo else ""


def lint_unknown_references(m: ProjectModel, known_ids: set[str]) -> list[str]:
    """With `--ids` (the lead's legend or the assembled map), every cross-reference in the fragment
    must resolve to the fragment's own definitions or the known universe — so an INVENTED id (the
    'tests target C112' class: plausible-looking, defined nowhere) dies in the authoring agent's
    turn instead of at the lead's final validate."""
    defined = set(all_elements(m)) | {g.id for g in m.happy_path} | known_ids
    out: list[str] = []
    # Gate the flag by NAMESPACE presence in the known universe (mirrors the actor/roles gate below):
    # a trace fragment's flow `uc` (`UC13`) is a real reference to a use case defined in the BEHAVIORAL
    # fragment, but a reduced trace legend lists only element ids (`C/E/D/R/S`), so without this gate
    # every trace fragment false-positives on its own `uc` values (the mcpolis build hand-worked around
    # this on ~7 agents). A namespace the universe doesn't cover at all can't be adjudicated — invented
    # vs. legit-but-omitted is indistinguishable. Element namespaces are always present, so
    # `tests target C112` still fails; a full-map legend contains `UC` ids, so an invented `UC99` inside
    # a behavioral fragment that defines `UC1..20` is still caught.
    known_prefixes = {_id_prefix(k) for k in defined}
    unresolved = sorted(r for r in _referenced_ids(m) - defined if _id_prefix(r) in known_prefixes)
    if unresolved:
        out.append(f"references ids defined neither in this fragment nor in --ids: "
                   f"{', '.join(unresolved)}")
    # A flow/sub-flow actor endpoint that is neither a backbone element id nor a KNOWN Role id is a
    # display name used where an Rn id belongs ("Team member" instead of R1). validate's actor check
    # self-disables in a roles-less trace fragment (roles live in the behavioral fragment), so without
    # the --ids universe this class survives to the lead's full validate — a whole reconcile phase
    # later, which both fresh builds hit and hand-patched. Gate on the universe actually HAVING roles:
    # a genuinely roles-less project may use display-name actors (a documented tolerance), and with no
    # role ids in --ids we can't tell "should be Rn" from "legit display name" — so only fire when the
    # legend proves roles exist, where a display-name endpoint is then unambiguously a mistake.
    if any(grammar.is_role_id(k) for k in known_ids):
        bad_actors: list[str] = []
        for label, steps in ([(f.uc, f.steps) for f in m.flows]
                             + [(sf.id, sf.steps) for sf in m.subflows]):
            for st in steps:
                if st.subflow:
                    continue  # a reference step's endpoints are the bridged backbone ids
                for end in (st.src, st.dst):
                    if end and not grammar.is_step_id(end) and not grammar.is_role_id(end) \
                            and end not in defined:
                        bad_actors.append(f"{label} step {st.n}: '{end}'")
        if bad_actors:
            out.append("actor endpoint(s) not a known Role id — reference the role by its Rn id from "
                       f"the legend, not a display name: {', '.join(bad_actors)}")
    return out


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
    # The roleless-C→D-verb nudge rides THIS non-blocking channel (never `lint_fragment_problems`,
    # which would promote it to a blocking problem — trap T7), so an authoring agent SEES it and
    # decides, without a legitimately-generic `uses` failing the lint.
    return warnings + _granularity_warnings(m) + roleless_cd_verb_warnings(m)


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
