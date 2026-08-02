#!/usr/bin/env python3
"""`coyodex assemble` — structured rows → the canonical model (the parallel-build assembler).

Build agents return STRUCTURED ROWS: each harvest/trace agent's output is saved verbatim as a
JSON *fragment* — a partial model holding a subset of the top-level arrays (components, edges,
entities, …) and, in at most one fragment, the header singletons (title / goal / commit /
committed / built). This command validates every fragment against the schema (one bad fragment
fails ALONE, with its file and JSON path named — the whole point of assembling with a tool),
merges them (arrays concatenate in argument order; a duplicate ID across fragments is an ERROR,
never a silent overwrite), and writes the canonical `project-map.json` plus its generated markdown
view. No HTML file is written: the interactive diagram is built on demand by `coyodex serve`. The
LLM never hand-authors the stored format: validity is guaranteed here, by the serializer.

A fragment is the model document minus the strictness that only the WHOLE map needs: `format` is
optional in a fragment, every top-level field is optional, and cross-fragment references are NOT
resolved here — that is `coyodex validate`'s job on the assembled result (the usual invariant
`validate --check-sources → audit → render` still runs after assembly). Stdlib-only.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import MISSING, fields, is_dataclass
from pathlib import Path
from typing import get_args, get_origin, get_type_hints

from coyodex import grammar
from coyodex.model import (
    FORMAT,
    ID_ARRAYS,
    ID_SHAPE,
    Edge,
    EntryPoint,
    ExtraSection,
    Flow,
    FlowStep,
    MessagingRow,
    ModelError,
    ProjectModel,
    _build,
    _normalize_subflow_title,
    load_model,
    remap_element_ids,
    to_canonical_json,
)
from coyodex.reporting import shown as _shown
from coyodex.reconcile import (
    ReconcileError,
    apply_reconcile,
    load_reconcile,
    validate_reconcile,
)
from coyodex.validate_model import unbacked_entity_steps

# Top-level NON-list fields, merged one-per-map with a conflict report. `grounding` belongs here:
# it is written by the Phase-4 reconcile as its own fragment, and omitting it meant `assemble`
# silently dropped the field on the only code path that writes a map — so the coverage record could
# never survive to the committed model, and `validate` then reported the map as never grounded.
_SINGLETONS = ("title", "goal", "commit", "committed", "built", "tests_note", "grounding")

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
    """A Phase-4 verdicts file ({"grounding": [row, …]}), not a build fragment.

    The discriminator is the TYPE of `grounding`, not its presence: a verdicts file holds a LIST of
    per-claim rows, the grounding FRAGMENT `grounding write` emits holds the record OBJECT, and both
    files carry that one key and nothing else. Keying on "shares no fragment field" instead — the
    first attempt — made this unconditionally False, because `grounding` is itself a `ProjectModel`
    field and so always intersected `_FRAGMENT_KEYS`: the skip below never once fired, and a verdicts
    file swept into the glob failed the build with a confusing schema error rather than the note that
    names it. (A real fragment carrying other sections alongside a stray `grounding` is still caught
    by the second clause and treated as a fragment.)"""
    try:
        obj = json.loads(text)
    except ValueError:
        return False
    return (isinstance(obj, dict) and isinstance(obj.get("grounding"), list)
            and not (set(obj) - {"grounding"}) & _FRAGMENT_KEYS)


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
    _normalize_subflow_title(data)  # `subflows[].title` alias — the shape agents guess by analogy
    # with Flow; five identical lint failures in one live rebuild (see model._normalize_subflow_title)
    m = _build(data, ProjectModel, label)
    for attr, prefix in ID_ARRAYS.items():
        for i, el in enumerate(getattr(m, attr)):
            eid = el.id
            good = bool(ID_SHAPE.match(eid)) and re.match(r"[A-Z]+", eid).group(0) == prefix  # type: ignore[union-attr]
            if not good:
                raise ModelError(f"{label}: $.{attr}[{i}].id: '{eid}' is not a valid {prefix}-id "
                                 f"(a schema id is the prefix + digits only, e.g. {prefix}3)")
    return m


def load_map_or_fragment(path: Path) -> tuple[ProjectModel, frozenset[str] | None]:
    """Load either an assembled map or a build FRAGMENT, and say which it was.

    Returns `(model, present_keys)`; `present_keys` is the fragment's own top-level key set, or None
    for a full map. Read-only tools (`dump`) can ignore it; a writer (`fix`) must pass it back to
    `dump_preserving` — see why there.

    A fragment is recognised by having no `format` key: `load_fragment` defaults it, which is the
    whole reason an agent can author a partial file. This exists because there was NO read path for a
    fragment at all: `dump` and `fix` both went through `load_model`, which requires `format`, so a
    build inspecting or editing its own fragments had nothing to use and wrote `python3 - <<'EOF'`
    heredocs instead — about fifteen times in one live build, against the method's own instruction to
    use `dump`."""
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ModelError(f"{path.name}: not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ModelError(f"{path.name}: top level: expected an object")
    if "format" in data:
        return load_model(text), None
    return load_fragment(text, path.name), frozenset(data)


def expand_directories(paths: list[Path], notes: list[str]) -> list[Path]:
    """Replace a bare DIRECTORY argument with its sorted `*.json` children.

    A directory is what an operator types first, and both commands used to die on the raw
    `[Errno 21] Is a directory` the reader raises. `--help` shows a glob but never says a bare
    directory is refused, so the failure reads as "this command is broken" rather than "add
    `/*.json`" — a live build lost a turn to it on `reconcile`, and `assemble` (printed far more
    often in method.md) had the same edge.

    A path ENDING IN `.json` is never expanded, even when it is a directory: `inner.json/` swept up
    by the caller's own glob must keep raising, or the glob form and the bare-directory form would
    silently disagree about the file set while both exit 0.

    `sorted()` is CODEPOINT order and the shell's glob is locale collation, so the two differ on any
    name leading with an uppercase letter or `_`. Argument order is load-bearing — dedup survivors
    are first-occurrence-in-argument-order — so the expansion is REPORTED rather than claimed to
    match the shell."""
    out: list[Path] = []
    for p in paths:
        if p.is_dir() and p.suffix != ".json":
            children = sorted(p.glob("*.json"))
            out.extend(children)
            notes.append(f"note: {p} expanded to {len(children)} fragment(s), in codepoint order — "
                         f"the shell's glob may order them differently under a non-C locale, and "
                         f"argument order decides which duplicate id survives")
        else:
            out.append(p)
    return out


def load_fragment_paths(paths: list[Path]) -> tuple[list[tuple[str, ProjectModel]],
                                                    list[str], list[str]]:
    """Read fragment FILES into `merge_fragments` parts. Returns `(parts, notes, errors)`.

    Every path is attempted before returning, so one malformed fragment does not hide the next four —
    the lead re-pings all the guilty agents in one round instead of discovering them one build cycle
    at a time. Printing is the caller's job: `assemble` fails the build on `errors`, `reconcile` does
    the same, and both surface `notes` unchanged.

    Shared because `reconcile` reads the SAME fragments `assemble` does. It used to demand an
    assembled map, which cannot exist yet at the moment a build needs the reconcile file — the
    circular dependency that made every build hand-write `reconcile.json` instead (nine in a row).
    One loader means the verdicts-file skip and the read errors can never drift between the two."""
    parts: list[tuple[str, ProjectModel]] = []
    notes: list[str] = []
    errors: list[str] = []
    for p in expand_directories(paths, notes):
        if p.name.endswith(".draft.json"):
            # The harvest contract tells agents to write `<path>.draft.json` while a fragment is
            # half-written, promising "the draft suffix keeps it out of the assemble glob". It did
            # not: `*.draft.json` matches `*.json`, and nothing here looked at the name. A build was
            # one mistimed assemble away from merging a truncated fragment.
            notes.append(f"note: skipping {p.name} — a draft, still being written")
            continue
        if not p.exists():
            errors.append(f"{p} not found")
            continue
        try:
            # Guarded on purpose: a directory swept up by the glob, a permission error or a bad
            # encoding used to raise straight out of the loop, so every remaining path went
            # unreported and the promise above ("every path is attempted") was false.
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            errors.append(f"{p}: cannot read: {e}")
            continue
        try:
            parts.append((p.name, load_fragment(text, p.name)))
        except ModelError as e:
            if _is_verdicts_file(text):
                notes.append(f"note: skipping {p.name} — a Phase-4 verdicts file, not a build "
                             f"fragment (keep verdicts out of build-fragments/ or feed them to "
                             f"`anchor-drift` / `fix apply-drift`, not `assemble`)")
                continue
            errors.append(str(e))
    return parts, notes, errors


def _element_types() -> dict[str, type]:
    """`{"components": Component, "edges": Edge, …}` — derived from `ProjectModel`'s annotations, not
    hard-coded, so a new section joins it automatically instead of silently falling back to "no
    defaults known" (which would quietly stop pruning that section)."""
    out: dict[str, type] = {}
    for name, hint in get_type_hints(ProjectModel).items():
        args = get_args(hint)
        if get_origin(hint) is list and args and isinstance(args[0], type) and is_dataclass(args[0]):
            out[name] = args[0]
    return out


def _prune_defaults(value: object, cls: type | None = None) -> object:
    """Drop keys whose value is just the dataclass default, recursively.

    Without this a fragment survives its own round-trip but every ELEMENT inside it fattens: a
    four-key component comes back with all thirteen fields, nulls and empty lists included. No value
    is lost, but a one-line `fix` then produces a diff across every row it touched, which buries the
    actual edit — and an author reading the file afterwards cannot tell what the tool changed."""
    if isinstance(value, list):
        # `cls` describes the list's ELEMENTS, so it must be carried through the recursion — dropping
        # it here silently disabled all pruning while every test but one still passed.
        return [_prune_defaults(v, cls) for v in value]
    if not isinstance(value, dict):
        return value
    defaults: dict[str, object] = {}
    if cls is not None:
        for f in fields(cls):                     # type: ignore[arg-type]
            if f.default is not MISSING:
                defaults[f.name] = f.default
            elif f.default_factory is not MISSING:  # type: ignore[misc]
                defaults[f.name] = f.default_factory()  # type: ignore[misc]
    out: dict[str, object] = {}
    for k, v in value.items():
        if k in defaults and v == defaults[k]:
            continue
        out[k] = _prune_defaults(v)
    return out


def dump_preserving(m: ProjectModel, present_keys: frozenset[str] | None) -> str:
    """Serialise `m`, keeping a fragment a FRAGMENT.

    `to_canonical_json` writes the whole model shape, so round-tripping a one-section fragment
    through it materialises all 29 sections as empty arrays. That is not cosmetic: a fragment's key
    set IS its ownership claim, and an agent's file that suddenly declares every section can make the
    merge attribute sections nobody authored. So for a fragment only the keys it already had are
    written back, and only the fields that carry a non-default value (`_prune_defaults`) — a fragment
    edit should read as the edit, not as a rewrite of every row it touched."""
    text = to_canonical_json(m)
    if present_keys is None:
        return text
    data = json.loads(text)
    types = _element_types()
    kept: dict[str, object] = {}
    for k, v in data.items():
        if k not in present_keys:
            continue
        kept[k] = _prune_defaults(v, types.get(k))
    return json.dumps(kept, indent=2, ensure_ascii=False) + "\n"


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
    chan_merged = _merge_duplicate_messaging(out, problems)   # two agents, same example row
    edges_before_dup = len(out.edges)
    _merge_duplicate_edges(out)  # LAST: dep-merge / actor-strip / component re-point can create exact dups
    eps_before_dup = len(out.entry_points)
    _mint_entry_point_ids(out)   # after every merge, so the minted range has no gaps
    extras_merged = _merge_extras_headings(out)
    if stats is not None:
        stats["actor_edges_stripped"] = actor_stripped
        stats["components_merged"] = comp_merged
        stats["messaging_rows_collapsed"] = chan_merged
        stats["duplicate_edges_collapsed"] = edges_before_dup - len(out.edges)
        stats["duplicate_entry_points_collapsed"] = eps_before_dup - len(out.entry_points)
        stats["extras_sections_merged"] = extras_merged
    return out, problems


def _merge_extras_headings(m: ProjectModel) -> int:
    """One section per heading. Returns how many duplicate sections were folded away.

    Extras arrive one per contributing fragment and were simply concatenated, so a live map shipped
    five `Entry-point coverage` sections, three `Balance exceptions` and two `Coverage exceptions`,
    each with different content. That is more than a reading annoyance:

      * `record.append_line` resolves a heading with `next(...)` — the FIRST section. With five
        sections a `--replace` aimed at a line in the third finds the first, matches no prefix and
        reports "nothing replaced", so the documented way to correct a record silently does nothing.
      * a reader of `project-map.md` meets the same heading repeatedly and has no way to know which
        copy the checks read.

    Bodies are concatenated in fragment-argument order, which is the order the reader already sees,
    and blank bodies are dropped so a placeholder section cannot leave a stray blank line. Matching
    is the same case/space-tolerant rule `record` and the readers use — deliberately shared rather
    than a third implementation of "is this the same heading"."""
    from coyodex.record import _resolve_heading
    by_key: dict[str, ExtraSection] = {}
    order: list[str] = []
    for sec in m.extras:
        canonical, _complaint = _resolve_heading(sec.heading)
        key = canonical.strip().lower()
        body = sec.body.strip("\n")
        if key not in by_key:
            by_key[key] = ExtraSection(heading=canonical, body=body)
            order.append(key)
            continue
        keep = by_key[key]
        if body:
            keep.body = f"{keep.body}\n{body}" if keep.body.strip() else body
    merged = len(m.extras) - len(order)
    m.extras = [by_key[k] for k in order]
    return merged


def _merge_duplicate_messaging(m: ProjectModel, problems: list[str]) -> int:
    """Collapse `messaging` rows that are unambiguously the SAME channel, unioning their participants.

    Two agents writing the same channel is correct input, not an error: the trace prompts for two
    different slices embedded the same literal example row, both agents dutifully wrote it, and
    `validate` then BLOCKED the build on `Duplicate messaging channel name(s)`. (`assemble` itself
    exits 0 — it is validate that blocks.) The lead hand-merged, and a hand merge picks a survivor
    where a union keeps what both agents actually found.

    IDENTITY IS `(name, broker)`, not the name alone. Two rows named `jobs` on brokers `D1` and `D9`
    are almost certainly two channels, and silently collapsing them would resolve a real conflict by
    fragment-filename order. A row with no broker is compatible with a named one (in-process is the
    default, so an unset field is "not stated" rather than "different"). Anything genuinely
    contradictory — two different non-empty `kind`, `payload` or `source` — is reported as a merge
    PROBLEM, the same way a singleton stated twice with different values already is, rather than
    guessed at. `_merge_duplicate_components` refuses an ambiguous identity for the same reason.

    Rows are rebuilt rather than mutated: `merge_fragments` extends the FRAGMENTS' own lists into the
    output, so writing through a survivor would edit the caller's fragment objects and make a second
    merge of the same parts produce a different map."""
    order: list[tuple[str, str]] = []
    groups: dict[tuple[str, str], list[MessagingRow]] = {}
    for row in m.messaging:
        name = row.name.strip()
        key = (name, row.broker.strip())
        # A broker-less row joins a named-broker group for the same channel when there is exactly one.
        if not key[1]:
            candidates = [k for k in groups if k[0] == name]
            if len(candidates) == 1:
                key = candidates[0]
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(row)
    merged: list[MessagingRow] = []
    collapsed = 0
    for key in order:
        rows = groups[key]
        first = rows[0]
        if len(rows) == 1:
            merged.append(first)
            continue
        collapsed += len(rows) - 1
        pubs: list[str] = []
        cons: list[str] = []
        scalars: dict[str, str] = {}
        for row in rows:
            pubs = _union_ids(pubs, row.publishers)
            cons = _union_ids(cons, row.consumers)
            for fname in ("kind", "broker", "payload", "source"):
                val = (getattr(row, fname, "") or "").strip()
                if not val:
                    continue
                prev = scalars.get(fname)
                if prev is None:
                    scalars[fname] = val
                elif prev != val:
                    problems.append(
                        f"messaging channel '{key[0]}' is declared more than once with different "
                        f"`{fname}` values ({prev!r} vs {val!r}) — either these are two different "
                        f"channels (give them different names) or one row is wrong. `assemble` unions "
                        f"participants for the same channel but will not choose between conflicting "
                        f"{fname} values.")
        merged.append(MessagingRow(name=key[0], publishers=pubs, consumers=cons,
                                   **{f: scalars.get(f, "") for f in
                                      ("kind", "broker", "payload", "source")}))
    m.messaging = merged
    return collapsed


def _union_ids(first: list[str], second: list[str]) -> list[str]:
    """First-seen order, no duplicates — a participant list is a set with a stable reading order."""
    out = list(first)
    for x in second:
        if x not in out:
            out.append(x)
    return out


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


def _entry_point_identity(ep: EntryPoint) -> tuple[str, str, str, str]:
    """An entry point's CONTENT identity — the FULL anchor (line included), the trigger, the owning
    component and the kind, all normalized.

    Every part of that is load-bearing, and the first revision of this function had none of it right.
    It called `strip_anchor`, which DROPS the line (`routes.py:40` -> `routes.py`), so identity was
    really `(file, trigger)` — while the docstring claimed the trigger was there to separate rows
    "registered on the same line". Two genuinely different surfaces anywhere in one router file with
    the same trigger text therefore merged, and the survivor kept only ONE component, kind and
    activation: a `[cron] POST /jobs @ routes.py:99` on C2 vanished behind a `[http-route] POST /jobs
    @ routes.py:40` on C1. A deleted row can never be reported as unclaimed, never appears under
    "Triggered by", and never reaches `--emit-unclaimed`.

    Over-merging is the dangerous direction here — a lost surface is invisible, a duplicated one is
    merely noisy — so the key is deliberately conservative, the same "only an exact identity match
    merges" discipline `_dep_identity` uses."""
    return (ep.source.strip().lower(),
            " ".join((ep.trigger or "").split()).lower(),
            ep.component.strip(),
            " ".join((ep.kind or "").split()).lower())


def _mint_entry_point_ids(m: ProjectModel) -> None:
    """Dedup entry points by content, then assign `EPn` in surviving order.

    Entry points are the one element family whose ids are NOT authored. Harvest agents already juggle
    pre-allocated C/D/E/SF ranges, and nothing references an entry point until synthesis — the
    `use_case.entry_points` trigger link is written by `reconcile`, after this runs — so a fifth range
    would buy nothing and make an overlap a hard build failure. Instead fragments leave `id` empty and
    assembly mints it here, deterministically from argument order.

    Dedup matters independently: unlike components, deps, messaging and edges, entry points were
    simply concatenated, so two harvest slices covering the same router shipped the same route twice.

    NUMBERING IS BY CONTENT, NOT ARGUMENT ORDER. The first revision numbered survivors in
    first-occurrence order like every other dedup, and that made the ids depend on the order the
    fragments happened to be passed in. Since `use_case.entry_points` is authored SEPARATELY (via
    `reconcile`, against the ids a previous assemble produced), swapping two fragments silently
    re-pointed a use case at a different front door — measured: `POST /orders` and
    `DELETE /admin/wipe-database` traded ids, the use case claimed the wrong one, validate resolved
    it happily and the warning count did not move. Sorting by the content key removes that whole
    class: the same set of surfaces gets the same ids however the fragments are ordered.

    RESIDUAL RISK, deliberately left: the ids are order-independent, not ADD-stable. Harvesting a
    NEW surface that sorts before an existing one still shifts the numbers after it, so a reconcile
    file authored against an older harvest can still mis-point. The durable fix is a content witness
    beside the id (`{"id": "EP1", "source": "orders.py:9"}`) that `validate_reconcile` checks — until
    that lands, re-author `entry_points` whenever the entry-point set changes."""
    seen: dict[tuple[str, str, str, str], EntryPoint] = {}
    kept: list[EntryPoint] = []
    for ep in m.entry_points:
        ident = _entry_point_identity(ep)
        if not ident[0]:            # no source anchor → not identifiable, keep as its own row
            kept.append(ep)
            continue
        if ident in seen:
            continue                # exact same surface, already recorded
        seen[ident] = ep
        kept.append(ep)
    # Anchorless rows have no content key to sort by, so they keep authored order and go last —
    # they are the un-identifiable tail, and giving them low numbers would let an unanchored row
    # shuffle the ids of every real surface.
    anchored = sorted((ep for ep in kept if ep.source.strip()), key=_entry_point_identity)
    loose = [ep for ep in kept if not ep.source.strip()]
    ordered = anchored + loose
    for n, ep in enumerate(ordered, start=1):
        ep.id = f"EP{n}"
    m.entry_points = ordered


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


# Ignored inside `<out>/.gitignore`: per-run scratch, per-run reports, and the developer-only archive
# of previous maps (`dev-rebuilds/`, written by `coyodex-eval archive` — a coyodex-developer
# convention, never a user artifact, and never committed). `finalize-report.*` is
# regenerated by every `coyodex finalize`, so committing it would put a diff on every build; it is a
# working artifact to READ, not a deliverable. Listed here so the command that creates it also owns
# its lifecycle, instead of leaving it to be swept up by someone's `git add -A`.
_GITIGNORE_KEEP: tuple[str, ...] = ("build-fragments/", "finalize-report.json",
                                   "finalize-report.md", "dev-rebuilds/")
# `preindex.json` is a COMMITTED artifact (the viewer's symbol search reads it, pinned to the map's
# commit), so it must NOT be ignored. Strip any stray ignore line (an older build, a hand edit) so it
# can't drift back out of version control. Match the plain name and a root-anchored form.
_GITIGNORE_DROP = {"preindex.json", "/preindex.json"}


def ensure_fragments_ignored(out_dir: Path) -> bool:
    """Normalize `<out>/.gitignore`: ensure every per-run artifact IS ignored (`build-fragments/`, the
    agents' scratch dir, and `finalize-report.{json,md}`, rewritten on every pre-commit read) so a build
    never dirties the tree, and ensure `preindex.json` is NOT ignored so the committed pre-index the
    viewer relies on stays in version control. Any other lines are left untouched. Returns True when
    the file changed (created, an entry added, or a stray preindex ignore stripped)."""
    gi = out_dir / ".gitignore"
    old_lines = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
    new_lines = [ln for ln in old_lines if ln.strip() not in _GITIGNORE_DROP]
    present = {ln.strip() for ln in new_lines}
    for entry in _GITIGNORE_KEEP:
        if entry not in present:
            new_lines.append(entry)
    if new_lines == old_lines:
        return False
    gi.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return True


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "-h" in argv or "--help" in argv or not argv:
        print("usage: coyodex assemble <fragment.json>... --out <dir> [--reconcile <file>]\n\n"
              "Merge build agents' structured-row fragments into the canonical project-map.json\n"
              "(+ the generated markdown view; the diagram is served, never written) in <dir>.\n"
              "Each fragment is a PARTIAL model (any subset of the top-level arrays; one header\n"
              "fragment may carry title/goal/commit). A malformed fragment or a duplicate ID\n"
              "fails loudly with the fragment named — nothing is silently fixed up; run\n"
              "`coyodex validate` on the result to catch anything else wrong.\n\n"
              "--reconcile <file>: a declarative reconcile input applied AFTER the merge (and after\n"
              "  entity-edge derivation), BEFORE the write — so a re-assemble always re-applies it.\n"
              "  `set` bulk-assigns subsystem/subdomain/runs_in/bucket; `drop_edges` removes refuted\n"
              "  edges and heals the flow steps that rode them. Keep this file OUTSIDE\n"
              "  build-fragments/ (e.g. .coyodex/reconcile.json) so the fragment glob does not sweep it.\n"
              "  The shape, in full (generate the `set` half with `coyodex reconcile --rules`):\n"
              "    {\n"
              '      "set": [ {"ids": ["C1","C2"], "subsystem": "S3"},\n'
              '               {"ids": ["C40"], "runs_in": ["worker"]},\n'
              '               {"ids": ["E7"], "subdomain": "SD2"},\n'
              '               {"ids": ["D5"], "bucket": "Data & storage"} ],\n'
              '      "drop_edges": [ {"src": "C21", "verb": "persists", "dst": "E33"},\n'
              '                      {"src": "C7", "verb": "calls", "dst": "C9",\n'
              '                       "drop_steps": true},\n'
              '                      {"src": "C4", "verb": "reads", "dst": "E2",\n'
              '                       "repoint": "E5"} ]\n'
              "    }\n"
              "  A `drop_edges` entry defaults to REPORTING the flow steps that rode the edge; add\n"
              "  `drop_steps: true` to remove them, or `repoint: <id>` to re-point them. A report-only\n"
              "  C→E drop leaves the step behind, and the NEXT assemble re-derives the edge from it —\n"
              "  so heal it, or the drop does not stick. Zero matches WARNS, never fails.\n\n"
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
    parts, notes, errors = load_fragment_paths(frags)
    for note in notes:
        print(note, file=sys.stderr)
    for err in errors:
        print(f"ERROR: {err}", file=sys.stderr)
    if errors:
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
        shown = _shown(derived, 8)   # via the shared helper, so a report mode can widen it
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
        # The unhealed-riding-step count is repeated here AND carried in `_assemble_digest`'s `ops:`
        # string. The digest is the one that matters: this note is line 9 of 13 on a fresh assemble,
        # so `| tail -4` — how a live build actually read this output — cuts it, and the two orphaned
        # steps only surfaced a round later at validate, costing a fragment edit, a re-assemble and a
        # re-run of apply-drift. Repeating it costs a clause and covers the reader who sees only the
        # head as well as the one who sees only the tail.
        unhealed = rec_stats.get("reconcile_riding_unhealed", 0)
        unhealed_tail = (
            f" {unhealed} flow step(s) still attribute a dropped edge and are NOT healed — heal them "
            f"with `drop_steps` / `repoint` (a report-only C→E drop leaves the step, which the next "
            f"assemble re-derives into the edge you just dropped)."
            if isinstance(unhealed, int) and unhealed else "")
        print(f"note: reconcile applied — set {{{set_summary}}}; "
              f"drop_edges: {rec_stats.get('reconcile_edges_dropped', 0)} edge(s); "
              f"keep_edges: {rec_stats.get('duplicate_edges_resolved', 0)} duplicate(s) resolved; "
              f"set_anchors: {rec_stats.get('anchors_corrected', 0)} anchor(s) "
              f"corrected.{unhealed_tail}")
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
    if stats.get("messaging_rows_collapsed"):
        ops.append(f"messaging rows collapsed {stats['messaging_rows_collapsed']}")
    if stats.get("extras_sections_merged"):
        ops.append(f"extras sections merged {stats['extras_sections_merged']}")
    sc = rec_stats.get("reconcile_set", {})
    if isinstance(sc, dict) and any(sc.values()):
        ops.append("reconcile set " + "/".join(f"{k}:{v}" for k, v in sc.items() if v))
    if rec_stats.get("duplicate_edges_resolved"):
        # `keep_edges` removed 51 edges on a real map and the digest said nothing — the same silent
        # delta this directive was added to stop. It belongs beside drop_edges, not nowhere.
        ops.append(f"reconcile keep_edges {rec_stats['duplicate_edges_resolved']}")
    if rec_stats.get("reconcile_edges_dropped"):
        ops.append(f"reconcile drop_edges {rec_stats['reconcile_edges_dropped']}")
    if rec_stats.get("anchors_corrected"):
        # Same reason as keep_edges above. `set_anchors` exists because 14 corrected anchors were
        # once lost silently; applying them silently is the same failure with the sign flipped.
        ops.append(f"reconcile set_anchors {rec_stats['anchors_corrected']}")
    # Unhealed riding steps belong HERE, in the digest, not on the reconcile note further up: the
    # note is line 9 of 13 on a fresh assemble, so `| tail -4` (how a live build read this output)
    # cuts it, while the digest is always in the last three lines. A report-only `drop_edges` that
    # leaves steps behind is a pending edit — the next assemble re-derives the C→E edge from the
    # surviving step — so it has to reach the reader who only sees the tail.
    if rec_stats.get("reconcile_riding_unhealed"):
        ops.append(f"UNHEALED riding steps {rec_stats['reconcile_riding_unhealed']} "
                   f"(heal with drop_steps/repoint)")
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
