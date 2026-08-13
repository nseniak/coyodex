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
from coyodex.model import ID_SHAPE, ModelError, ProjectModel, access_rules, all_elements
from coyodex.validate_model import (
    _cadence_row_warnings,
    _check_activations,
    _check_anchor_format,
    _check_edges,
    _check_entry_kinds,
    _check_extra_conventions,
    _check_flows,
    _check_messaging,
    _check_states,
    _check_stores,
    _granularity_warnings,
    confidence_warnings,
    _referenced_ids,
    check_anchor_existence_model,
    check_domain_relations,
    check_entity_sources_model,
    rule_row_problems,
    domain_card_shape_problems,
    duplicate_security_warnings,
    roleless_cd_verb_warnings,
    subflow_refcount_warnings,
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
                                "defined element id (UC/HP/CAP/S/SD/SF/C/D/E/R/EP + digits)")
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


def lint_fragment_problems(m: ProjectModel, repo_root: Path | None,
                           known_ids: set[str] | None = None) -> list[str]:
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
    # The per-card SHAPE rules (meaning / source / fields / field types), shared verbatim with
    # `validate`. Every one is row-local, so a fragment CAN answer them — they simply ran only on
    # the assembled map, which is how a T5 fragment linted clean and then failed the lead's
    # `validate` a phase later, eight cards at a time.
    problems += domain_card_shape_problems(m.entities)
    problems += _check_stores(m)  # row-local store-shape rules (dep id shape, closed mode); the
    # folded-dep check self-disables when the fragment doesn't define the dep (it can't resolve it)
    state_problems, _state_warnings = _check_states(m)  # row-local machine rules (empty list, dup
    problems += state_problems                          # names, undeclared transition endpoint)
    msg_problems, _msg_warnings = _check_messaging(m)   # row-local channel rules (id shapes,
    problems += msg_problems                            # dup names); the backing-edge advisory
    # stays out — the edges usually live in another fragment
    edge_problems, edge_warnings = _check_edges(m)
    problems += edge_problems + edge_warnings
    # Flow rules (missing step `where`, duplicate step n, missing phrase/endpoint) fail in the trace
    # agent's own turn, not a phase later at the lead's `validate`. Safe on a partial fragment: the
    # actor-id check self-disables when the fragment defines no roles. Warnings promoted, like edges'.
    flow_problems, flow_warnings = _check_flows(m)
    # A step referencing a sub-flow DEFINED IN A SIBLING FRAGMENT is legal (per-agent SF id ranges
    # make collisions impossible; the map assembles whole) — but this fragment can't see it, so the
    # undefined-sub-flow problem false-fires. With an `--ids` universe that KNOWS the SF id, drop
    # that problem; without one, it stands (an invented SF must still die here). A live rebuild
    # duplicated a shared trace inline because this filter didn't exist.
    if known_ids:
        flow_problems = [p for p in flow_problems
                         if not (( mo := re.search(r"references undefined sub-flow '(SF\d+)'", p))
                                 and mo.group(1) in known_ids)]
    problems += flow_problems + flow_warnings
    problems += _check_reference_shapes(m)
    # The T7 rule rules (a statement, at least one site, an anchored OPERATIVE line per site) — all
    # row-local, so a per-block fragment CAN answer them. Here rather than only at the lead's
    # `validate` for the same reason the flow rules are: a block agent writing eight rules should
    # fail on its own bad anchor in its own turn, not eight rules later in someone else's report.
    # The WHOLE-MAP rules stay out — the sweep canary (a fragment holds one block's rules, so every
    # other block's decisions would read as debt) and the `Component.files` gate (they live in a
    # different fragment, so a block agent would fail its lint on a defect it cannot fix).
    problems += rule_row_problems(m)
    # `block` is a SYNTHESIS assignment, exactly like `capability`: a `BLK` id is minted before the
    # rules exist, and a re-synthesis that renumbers blocks must not silently re-point every rule.
    # The method says "never in the fragment"; without this the rule is prose, and a fragment
    # carrying `block` lints clean and assembles with the value intact.
    in_fragment = [r.id for r in m.rules if r.block]
    if in_fragment:
        problems.append(
            f"business rule(s) carry `block` in a fragment: {', '.join(in_fragment)} — block "
            "assignment goes through the synthesis `reconcile` (`coyodex reconcile`), never a "
            "fragment: BLK ids are minted before the rules exist, and a re-synthesis that "
            "renumbers them would leave these pointing at the wrong areas")
    if repo_root is not None:
        roots = [repo_root.resolve()]
        problems += check_anchor_existence_model(m, roots)
        problems += check_entity_sources_model(m, roots)
    return problems


def _legacy_security_warnings(m: ProjectModel) -> list[str]:
    """Advisory: a fragment authoring `security[]`. An auth surface is an `access` business rule
    now — the Security & auth table is a derived view of those. Nothing REJECTS a security row (a
    map built before the fold still loads and still renders its rows), so this is where a NEW build
    finds out, in the authoring agent's own turn rather than never."""
    if not m.security:
        return []
    return [f"{len(m.security)} `security[]` row(s) authored — an auth surface is a business rule "
            "with `access: true` now (T7), and the Security & auth table is a derived view of "
            "those. Write the decision, its enforcement site(s) and its `risk`; a security row is "
            "the legacy storage, kept only so a map built before the fold still renders."]


def _access_rule_risk_warnings(m: ProjectModel) -> list[str]:
    """Advisory: an `access: true` rule with no `risk`.

    method.md requires an auth surface to state "what is at stake as its `risk`", and before the fold
    every security row carried one. After it, two consecutive real builds shipped maps where NOT ONE
    rule of 69 and 96 had a risk — the rendered Security & auth table's Risk column was blank on
    every row — and nothing anywhere said so. Advisory rather than blocking, because a fragment
    author can legitimately be mid-draft, and because failing the lint on a pre-fold map's rules
    would block a rebuild that is otherwise improving the map."""
    naked = [r.id for r in access_rules(m) if not (r.risk or "").strip()]
    if not naked:
        return []
    return [f"{len(naked)} `access: true` rule(s) with an empty `risk`: {', '.join(naked[:12])}"
            + (" …" if len(naked) > 12 else "")
            + " — an auth surface must say what is at stake if it fails. The Security & auth table "
              "renders `risk` as its own column, so an empty one ships as a blank cell."]


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
    warnings += _legacy_security_warnings(m)
    # The roleless-C→D-verb nudge rides THIS non-blocking channel (never `lint_fragment_problems`,
    # which would promote it to a blocking problem — trap T7), so an authoring agent SEES it and
    # decides, without a legitimately-generic `uses` failing the lint. The entry-point-kind nudges
    # and the ROW-LOCAL cadence nudges (contradiction / inferred / dangling anchor) ride here too
    # (seeded-OPEN vocabulary and judgment-shaped signals — never fail a fragment); the per-kind
    # COVERAGE contract and the missing-cadence family do not (each relates the whole T4 inventory
    # to an extras heading another fragment may carry — vacuous per-fragment, like
    # `_completeness_warnings`).
    # The sub-flow refcount nudge rides here too — it is judgment-shaped AND per-fragment blind
    # (the other reference may live in a sibling fragment); promoting it to blocking made a live
    # rebuild inline three legitimate sub-flows and ship a fragment its author believed had passed.
    # `duplicate_security_warnings` rides here too: WITHIN one fragment a repeated surface is
    # answerable now, and the cross-fragment case (the common one) still surfaces at validate.
    return (warnings + _granularity_warnings(m) + roleless_cd_verb_warnings(m)
            + _check_entry_kinds(m) + _cadence_row_warnings(m) + subflow_refcount_warnings(m)
            + duplicate_security_warnings(m) + confidence_warnings(m)
            # Row-local: one rule's own `risk`, answerable by the block agent that wrote it.
            + _access_rule_risk_warnings(m))


# DELIBERATELY ABSENT: a per-fragment nudge about the entry-point per-kind COMPLETENESS statement.
# The information loss it would chase is real — on a live build all twelve harvest agents stated their
# per-kind completeness in their RETURN MESSAGE, no prompt asked for it in a fragment, and the lead's
# validate then flagged 13 kinds with no statement. It still does not belong here. A canonical-kind T4
# harvest fragment is CORRECT, `lint_fragment_warnings` is asserted EMPTY for one on purpose, and an
# advisory that fires on every such fragment is a nag on correct work. The fragment also cannot know
# whether the statement exists: the 'Entry-point coverage' heading is authored by the LEAD, in a
# different fragment. The fix is in the harvest PROMPT — the fragment template must ask for the
# statement — which is a method change, not a lint check. (Tried as a warning; reverted.)


#: How far a slice may miss its dispatched component budget before `--expect` says so. Wide on
#: purpose: the budget is a pre-read estimate, and a slice that finds 7 where 5 were guessed is
#: normal. What it catches is the systematic overshoot — on a live build the nine code slices were
#: dispatched with budgets summing to ~55 and delivered 86, every slice over, and nothing noticed
#: until the lead's granularity advisory said "86 vs a code-derived ~59" after assembly.
_BUDGET_LO, _BUDGET_HI = 0.5, 1.5


def _budget_warnings(m: ProjectModel, expect: int | None) -> list[str]:
    """Advisory: this fragment's component count against the budget its slice was dispatched with.

    Never blocking. The budget is the lead's estimate, and the authoring agent is the one holding the
    code — if it found more real components than the estimate, the estimate was wrong. The point is
    that the delta becomes visible to the agent that can explain it, in its own turn, instead of
    surfacing as an unattributable total after every fragment has been merged."""
    if expect is None or expect <= 0:
        return []
    n = len(m.components)
    if not n or _BUDGET_LO * expect <= n <= _BUDGET_HI * expect:
        return []
    direction = "over" if n > expect else "under"
    return [f"{n} component(s) against a dispatched budget of ~{expect} ({n / expect:.1f}x, {direction} "
            f"the {_BUDGET_LO:g}x-{_BUDGET_HI:g}x band) — if the slice really holds this many, say so "
            f"in your reply so the lead can record the altitude decision under a 'Balance exceptions' "
            f"extras heading; if it is drift, fold the near-duplicates into one component."]


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "-h" in argv or "--help" in argv or not argv:
        print("usage: coyodex lint-fragment [--repo <root>] [--ids <legend-or-map>] [--expect N]\n"
              "                             <fragment.json>...\n\n"
              "Self-check a build fragment BEFORE returning it: schema, anchor format, `extra`-key\n"
              "conventions, (with --repo) that every anchor's file exists, and (with --ids) that every\n"
              "cross-referenced id is defined in the fragment or the given id universe — pass the\n"
              "lead's legend (_legend.md) or the assembled project-map.json, so an INVENTED id dies\n"
              "here instead of at the lead's final validate. Reports all findings and exits non-zero\n"
              "on any, so an agent fixes its own rows in context instead of the lead hand-patching\n"
              "them after assembly.\n"
              "--expect N: the component budget this slice was dispatched with. Advisory: warns when\n"
              "  the fragment lands outside 0.5x-1.5x N, so the overshoot is visible to the agent that\n"
              "  caused it rather than only in the lead's granularity advisory after assembly.")
        return 0 if ("-h" in argv or "--help" in argv) else 2
    repo_root: Path | None = None
    known_ids: set[str] | None = None
    expect: int | None = None
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
                print("ERROR: --ids needs an existing legend/map file (or a directory of fragments)",
                      file=sys.stderr)
                return 2
            # any format works: the universe is every id-shaped token in the file (a markdown legend,
            # the assembled map, or a plain id list all read the same way). A DIRECTORY scans its
            # *.json/*.md files — pass `build-fragments/` so ids DEFINED by sibling fragments (a
            # trace agent's SF the legend predates) resolve instead of forcing inline duplication.
            ids_path = Path(argv[i])
            sources = (sorted([*ids_path.glob("*.json"), *ids_path.glob("*.md")])
                       if ids_path.is_dir() else [ids_path])
            known_ids = {t for src in sources
                         for t in re.findall(r"\b[A-Z]+\d+\b", src.read_text(encoding="utf-8"))
                         if ID_SHAPE.match(t)}
        elif a == "--expect":
            i += 1
            if i >= len(argv) or not argv[i].lstrip("+").isdigit():
                print("ERROR: --expect needs a component count (an integer)", file=sys.stderr)
                return 2
            expect = int(argv[i])
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
    unreadable = False
    for p in frags:
        # "cannot read it" and "it breaks a rule" are different answers, and they used to print the
        # same verdict: a wrong path produced `ERROR: … not found` followed by "LINT FAILED: fix the
        # rows above", sending the agent hunting for a rule violation in a file nobody opened. A
        # live build lost two turns to it, both times from running the command in another directory.
        if not p.exists():
            print(f"ERROR: cannot read {p} — no such file. (The fragment path and --repo are both "
                  f"resolved from the CURRENT directory.)", file=sys.stderr)
            unreadable = True
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            print(f"ERROR: cannot read {p}: {e}", file=sys.stderr)
            unreadable = True
            continue
        try:
            m = load_fragment(text, p.name)
        except ModelError as e:
            print(f"{p.name}: SCHEMA — {e}", file=sys.stderr)
            clean = False
            continue
        problems = lint_fragment_problems(m, repo_root, known_ids)
        if known_ids is not None:
            problems += lint_unknown_references(m, known_ids)
        if problems:
            clean = False
            for pr in problems:
                print(f"{p.name}: {pr}", file=sys.stderr)
        else:
            print(f"{p.name}: OK")
        # advisory warnings never fail the lint — heuristic nudges the agent can act on or ignore
        for w in lint_fragment_warnings(m) + _budget_warnings(m, expect):
            print(f"{p.name}: warning: {w}", file=sys.stderr)
    if unreadable:
        print("LINT DID NOT RUN on the file(s) above — they could not be read, so nothing was "
              "checked. This is not a rule violation; fix the path and re-run.", file=sys.stderr)
        return 2
    if not clean:
        print("LINT FAILED: fix the rows above before returning this fragment. "
              "(`warning:` lines are advisory heuristics — they do not fail the lint.)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
