#!/usr/bin/env python3
"""Tests for `coyodex audit` — the adversarial pass (L1 self-contradiction + L2 worklist).

The scenario maps are authored as schema-v1 markdown (a compact test notation) and converted
through the one remaining v1 reader (`convert_text`) into the model the audit actually reads —
so these tests exercise the LIVE pipeline (model audit), not the retired markdown audit.

Stdlib-only — no pytest required. Run either way (needs an editable install: `make deps`):
    python3 tests/test_audit.py        # built-in runner (prints pass/fail)
    pytest tests/test_audit.py         # if pytest is installed
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from coyodex import audit_model
from coyodex.convert_md import convert_text
from coyodex.model import to_canonical_json

AUDIT = [sys.executable, "-m", "coyodex.audit_model"]


def audit_md(md: str) -> list[audit_model.Finding]:
    """The L1 findings for a scenario map: convert the v1 test notation, audit the model."""
    return audit_model.audit_model(convert_text(md).model)


def l2(md: str) -> list[audit_model.WorkItem]:
    """The L2 worklist for a scenario map, through the same convert-then-model path."""
    return audit_model.l2_worklist_model(convert_text(md).model)


# --- builders -------------------------------------------------------------------
def make_precedence_map(bad: bool = True, create_verb: str = "persists") -> str:
    """Two use cases over one entity E1: UC1 READS the order, UC2 CREATES it (`create_verb`).
    `bad=True` orders the Golden Path read-then-create (the read-before-create shape); `bad=False`
    orders it create-then-read (clean). `create_verb` lets a test use a MUTATION verb (`writes`) to
    prove an update is NOT mistaken for a create. No `why:` lines, so the why-less check is a no-op."""
    gp = (
        "## Golden Path\n"
        + ("**GP1 — Andy views the order** *(UC1)*\n**GP2 — Adam creates the order** *(UC2)*\n\n"
           if bad else
           "**GP1 — Adam creates the order** *(UC2)*\n**GP2 — Andy views the order** *(UC1)*\n\n")
    )
    return (
        "## Use cases\n"
        "| ID | Use case | Actor | Trigger → Outcome |\n"
        "|---|---|---|---|\n"
        "| **UC1** | View order | Andy | opens -> sees |\n"
        "| **UC2** | Create order | Adam | submits -> stored |\n\n"
        "## T1\n"
        "| ID | Component | Purpose | Entry point | Depends on |\n"
        "|---|---|---|---|---|\n"
        "| **C1** | Viewer | x | f | E1 |\n"
        "| **C2** | Creator | x | f | E1 |\n\n"
        + gp +
        "## T5 — Domain model\n"
        "**E1 — Order** *(orders)*\n"
        "MEANING: a customer order\n"
        "SOURCE: [order.py](order.py#L1)\n\n"
        "## T6 — Use-case flows\n"
        "**UC1 — View order**\n"
        "1. Andy → C1 : views the order\n\n"
        "**UC2 — Create order**\n"
        "1. Adam → C2 : creates the order\n\n"
        "### edges\n"
        "| From | Verb | To | Why | Where |\n"
        "|---|---|---|---|---|\n"
        "| C1 | reads | E1 | show it | f#L1 |\n"
        f"| C2 | {create_verb} | E1 | store it | f#L2 |\n"
    )


def make_actor_mismatch_map(flow_actor: str = "Zoe") -> str:
    """UC1's declared Actor is Andy, but its flow opens with `flow_actor` — a mismatch when it isn't
    Andy (the two layers disagree about who drives the use case)."""
    return (
        "## Use cases\n"
        "| ID | Use case | Actor | Trigger → Outcome |\n"
        "|---|---|---|---|\n"
        "| **UC1** | View order | Andy | opens -> sees |\n\n"
        "## T1\n| ID | Component | Purpose | Entry point | Depends on |\n|---|---|---|---|---|\n"
        "| **C1** | Viewer | x | f |  |\n\n"
        "## Golden Path\n**GP1 — View the order** *(UC1)*\n\n"
        "## T6 — Use-case flows\n"
        "**UC1 — View order**\n"
        f"1. {flow_actor} → C1 : views the order\n"
    )


def make_actor_variant_map(declared: str, opening: str, roles: bool = False) -> str:
    """UC1's declared Actor is `declared`; its flow opens with `opening`. `roles=True` adds a Roles
    table containing only 'Andy', so an opener that is not a defined Role (a background trigger) is
    skipped. Covers the markdown / compound / background-trigger false-positive cases."""
    roles_tbl = (
        "## Roles (actors)\n| Role | Kind | What they want | Use cases they drive |\n"
        "|---|---|---|---|\n| **Andy** | human | see it | UC1 |\n\n" if roles else "")
    return (
        roles_tbl +
        "## Use cases\n"
        "| ID | Use case | Actor | Trigger → Outcome |\n"
        "|---|---|---|---|\n"
        f"| **UC1** | View order | {declared} | opens -> sees |\n\n"
        "## T1\n| ID | Component | Purpose | Entry point | Depends on |\n|---|---|---|---|---|\n"
        "| **C1** | Viewer | x | f |  |\n\n"
        "## Golden Path\n**GP1 — View the order** *(UC1)*\n\n"
        "## T6 — Use-case flows\n"
        "**UC1 — View order**\n"
        f"1. {opening} → C1 : views the order\n"
    )


def make_shared_read_map() -> str:
    """Three use cases whose flows all read E1 (via a component that reads it); E1 is never written on
    the path. Exercises per-entity dedup: exactly ONE read-never-created advisory, not three."""
    return (
        "## Use cases\n| ID | Use case | Actor | Trigger → Outcome |\n|---|---|---|---|\n"
        "| **UC1** | A | Andy | a -> b |\n| **UC2** | B | Andy | a -> b |\n"
        "| **UC3** | C | Andy | a -> b |\n\n"
        "## T1\n| ID | Component | Purpose | Entry point | Depends on |\n|---|---|---|---|---|\n"
        "| **C1** | A | x | f | E1 |\n| **C2** | B | x | f | E1 |\n| **C3** | C | x | f | E1 |\n\n"
        "## Golden Path\n**GP1 — A** *(UC1)*\n**GP2 — B** *(UC2)*\n**GP3 — C** *(UC3)*\n\n"
        "## T5 — Domain model\n**E1 — User** *(users)*\nMEANING: a user\nSOURCE: [u.py](u.py#L1)\n\n"
        "## T6 — Use-case flows\n"
        "**UC1 — A**\n1. Andy → C1 : reads the user\n\n"
        "**UC2 — B**\n1. Andy → C2 : reads the user\n\n"
        "**UC3 — C**\n1. Andy → C3 : reads the user\n\n"
        "### edges\n| From | Verb | To | Why | Where |\n|---|---|---|---|---|\n"
        "| C1 | reads | E1 | x | f#L1 |\n| C2 | reads | E1 | x | f#L2 |\n| C3 | reads | E1 | x | f#L3 |\n"
    )


def make_cc_routed_read_map() -> str:
    """The mcpolis bug shape, but the precondition read is routed through a `C→C` dependency: UC1's
    flow names only C1; C1 reads C3 (C→C); C3 reads E1 (C→E, but C3 is NOT in the flow). E1 is created
    at GP2. Audit CANNOT see the read (only C→E edges of flow-named components count) — a documented
    false negative that pins the limitation."""
    return (
        "## Use cases\n| ID | Use case | Actor | Trigger → Outcome |\n|---|---|---|---|\n"
        "| **UC1** | Sign in | Andy | a -> b |\n| **UC2** | Create org | Adam | a -> b |\n\n"
        "## T1\n| ID | Component | Purpose | Entry point | Depends on |\n|---|---|---|---|---|\n"
        "| **C1** | SignIn | x | f | C3 |\n| **C2** | OrgSvc | x | f | E1 |\n"
        "| **C3** | MemberStore | x | f | E1 |\n\n"
        "## Golden Path\n**GP1 — Sign in** *(UC1)*\n**GP2 — Create org** *(UC2)*\n\n"
        "## T5 — Domain model\n**E1 — Organization** *(orgs)*\nMEANING: tenant\nSOURCE: [o.py](o.py#L1)\n\n"
        "## T6 — Use-case flows\n"
        "**UC1 — Sign in**\n1. Andy → C1 : signs in\n\n"
        "**UC2 — Create org**\n1. Adam → C2 : creates org\n\n"
        "### edges\n| From | Verb | To | Why | Where |\n|---|---|---|---|---|\n"
        "| C1 | reads | C3 | resolve membership | f#L1 |\n"
        "| C3 | reads | E1 | membership→org | f#L2 |\n"
        "| C2 | persists | E1 | create org | f#L3 |\n"
    )


def make_backward_whyref_map() -> str:
    """GP1's `why:` cites GP2, which comes after it (a backward reference)."""
    return (
        "## Use cases\n"
        "| ID | Use case | Actor | Trigger → Outcome |\n"
        "|---|---|---|---|\n"
        "| **UC1** | A | Andy | a -> b |\n"
        "| **UC2** | B | Andy | a -> b |\n\n"
        "## T1\n| ID | Component | Purpose | Entry point | Depends on |\n|---|---|---|---|---|\n"
        "| **C1** | A | x | f |  |\n\n"
        "## Golden Path\n"
        "**GP1 — First** *(UC1)*\n"
        "why: needs the thing from GP2\n"
        "**GP2 — Second** *(UC2)*\n"
        "why: follows GP1\n\n"
        "## T6 — Use-case flows\n"
        "**UC1 — A**\n1. Andy → C1 : does a\n\n"
        "**UC2 — B**\n1. Andy → C1 : does b\n"
    )


def make_read_never_created_map() -> str:
    """A single step reads E9, which no step ever creates (an external/config entity) — advisory."""
    return (
        "## Use cases\n"
        "| ID | Use case | Actor | Trigger → Outcome |\n"
        "|---|---|---|---|\n"
        "| **UC1** | Load config | Andy | a -> b |\n\n"
        "## T1\n| ID | Component | Purpose | Entry point | Depends on |\n|---|---|---|---|---|\n"
        "| **C1** | Loader | x | f | E9 |\n\n"
        "## Golden Path\n**GP1 — Load the config** *(UC1)*\n\n"
        "## T5 — Domain model\n"
        "**E9 — AppConfig** *(config)*\nMEANING: config\nSOURCE: [c.py](c.py#L1)\n\n"
        "## T6 — Use-case flows\n**UC1 — Load config**\n1. Andy → C1 : loads config\n\n"
        "### edges\n| From | Verb | To | Why | Where |\n|---|---|---|---|---|\n"
        "| C1 | reads | E9 | config | f#L1 |\n"
    )


def make_whyless_map() -> str:
    """GP1 has a `why:`, GP2 does not — a non-initial step missing its precondition (warning)."""
    return (
        "## Use cases\n"
        "| ID | Use case | Actor | Trigger → Outcome |\n"
        "|---|---|---|---|\n"
        "| **UC1** | A | Andy | a -> b |\n"
        "| **UC2** | B | Andy | a -> b |\n\n"
        "## T1\n| ID | Component | Purpose | Entry point | Depends on |\n|---|---|---|---|---|\n"
        "| **C1** | A | x | f |  |\n\n"
        "## Golden Path\n"
        "**GP1 — First** *(UC1)*\n"
        "why: the start\n"
        "**GP2 — Second** *(UC2)*\n\n"
        "## T6 — Use-case flows\n"
        "**UC1 — A**\n1. Andy → C1 : does a\n\n"
        "**UC2 — B**\n1. Andy → C1 : does b\n"
    )


def make_l2_map() -> str:
    """A Security & auth table plus an `enforces` edge — the two L2-worklist sources."""
    return (
        "## Use cases\n| ID | Use case | Actor | Trigger → Outcome |\n|---|---|---|---|\n"
        "| **UC1** | Call | Andy | a -> b |\n\n"
        "## T1\n| ID | Component | Purpose | Entry point | Depends on |\n|---|---|---|---|---|\n"
        "| **C1** | Gate | x | f | C2 |\n| **C2** | Policy | x | f |  |\n\n"
        "### Security & auth\n"
        "| Surface | Who can reach | Auth check | Risk note |\n"
        "|---|---|---|---|\n"
        "| /api | admins | [require_admin](auth.py#L10) | escalation |\n\n"
        "### edges\n| From | Verb | To | Why | Where |\n|---|---|---|---|---|\n"
        "| C1 | enforces | C2 | policy | gate.py#L5 |\n"
    )


def make_l2_dep_map() -> str:
    """The whole broadened worklist on one map: an `enforces` edge (security, ranks first); a `C→D`
    `emits` into an EXPLICIT `datastore` and a `writes` into an UNTAGGED dep (both ground); a `uses`
    into an EXPLICIT `library` (skip — a false 'uses <lib>' is benign); a `C→E` `persists` (ownership);
    and a plain `C→C` `calls` (remaining). The `emits`-into-a-log-dep row is the audit→Elastic
    false-edge class."""
    return (
        "## Use cases\n| ID | Use case | Actor | Trigger → Outcome |\n|---|---|---|---|\n"
        "| **UC1** | Call | Andy | a -> b |\n\n"
        "## T2\n| ID | Dependency | Type | Kind | Purpose |\n|---|---|---|---|---|\n"
        "| **D1** | Elastic Cloud | search | datastore | log storage |\n"
        "| **D2** | logging | stdlib | library | app logs |\n"
        "| **D3** | Mystery | ? |  | unknown |\n\n"
        "### edges\n| From | Verb | To | Why | Where |\n|---|---|---|---|---|\n"
        "| C1 | enforces | C2 | policy | gate.py#L5 |\n"
        "| C1 | emits | D1 | ship logs | audit_repo.py#L8 |\n"
        "| C1 | uses | D2 | log lines | mod.py#L3 |\n"
        "| C1 | writes | D3 | dump | x.py#L1 |\n"
        "| C1 | persists | E1 | store | repo.py#L2 |\n"
        "| C1 | calls | C3 | rpc | client.py#L4 |\n"
    )


def make_duplicated_edge_map() -> str:
    """`make_l2_dep_map` with its C→D `emits` row DUPLICATED — the G4 dedupe shape (a repeated edge
    row must not become two skeptic tasks)."""
    return make_l2_dep_map() + "| C1 | emits | D1 | ship logs | audit_repo.py#L8 |\n"


def make_described_map() -> str:
    """Named components with file anchors, a named dep, and an entity card with SOURCE — so worklist
    claims can carry self-describing From/To detail (G1)."""
    return (
        "## T1\n| ID | Component | Purpose | Entry point | Depends on |\n|---|---|---|---|---|\n"
        "| **C1** | AuthGate | x | [gate.py](src/auth/gate.py#L10) |  |\n"
        "| **C2** | PolicyStore | x | [policy.py](src/policy.py#L5) |  |\n\n"
        "## T2\n| ID | Dependency | Type | Kind | Purpose |\n|---|---|---|---|---|\n"
        "| **D1** | Elastic | search | datastore | logs |\n\n"
        "## T5 — Domain model\n\n"
        "**E1 — Order** *(orders)*\nMEANING: m\nFIELDS: id:int\nSOURCE: [order.py](src/order.py#L1)\n\n"
        "### edges\n| From | Verb | To | Why | Where |\n|---|---|---|---|---|\n"
        "| C1 | enforces | C2 | policy | gate.py#L5 |\n"
        "| C1 | emits | D1 | logs | gate.py#L8 |\n"
        "| C2 | persists | E1 | store | policy.py#L9 |\n"
    )


def run_audit(md: str) -> tuple[int, str]:
    """Drive the audit CLI on the scenario map, converted to a model document first."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(to_canonical_json(convert_text(md).model))
        path = f.name
    r = subprocess.run([*AUDIT, path], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def _checks(md: str) -> dict[str, str]:
    """{check_name: severity} for the L1 findings on a map (direct engine call, no subprocess)."""
    return {f.check: f.severity for f in audit_md(md)}


# --- L1: read-before-create (advisory — lossy attribution, must not block) -------
def test_read_before_create_is_advisory() -> None:
    """It surfaces the read-then-create ordering, but as an ADVISORY — the component-granularity
    attribution has real false positives (the audit review), so it must never block a build."""
    checks = _checks(make_precedence_map(bad=True))
    assert checks.get("read-before-create") == "ADVISORY", checks


def test_read_before_create_does_not_block_the_cli() -> None:
    code, out = run_audit(make_precedence_map(bad=True))
    assert code == 0, out
    assert "read-before-create" in out and "AUDIT PASSED" in out, out


def test_correct_order_has_no_finding() -> None:
    """Regression guard: a create-then-read Golden Path is clean — no false positive."""
    assert audit_md(make_precedence_map(bad=False)) == []


def test_write_modeled_create_surfaces_read_before_create() -> None:
    """Finding F1 (2nd review): `writes` is create-OR-update ambiguous and the method uses it for
    creates (the live mcpolis map models 'create the admin membership' as a `writes` edge). A read
    before a later `writes` must still surface the ordering as read-before-create (advisory) — the
    signal must NOT be lost as read-never-created just because the verb was `writes` not `persists`."""
    checks = _checks(make_precedence_map(bad=True, create_verb="writes"))
    assert checks.get("read-before-create") == "ADVISORY", checks
    assert "read-never-created" not in checks, checks


def test_read_never_created_is_deduped_per_entity() -> None:
    """Finding F4 (2nd review): a shared entity read by many steps yields ONE advisory, not one per
    step (which scales to dozens on a real map with common User/Org/Config entities)."""
    dupes = [f for f in audit_md(make_shared_read_map())
             if f.check == "read-never-created"]
    assert len(dupes) == 1, dupes


def test_clean_map_passes_the_cli() -> None:
    code, out = run_audit(make_precedence_map(bad=False))
    assert code == 0, out
    assert "AUDIT PASSED" in out, out


def test_cc_routed_read_is_a_known_gap() -> None:
    """Finding 5: a precondition read routed through a `C→C` dependency is invisible to the C→E-only
    attribution — a documented false negative. Pin it so the limitation is explicit."""
    assert "read-before-create" not in _checks(make_cc_routed_read_map())


# --- L1: actor-attribution (advisory, guarded against the confirmed false positives) --
def test_actor_attribution_mismatch_is_advisory() -> None:
    assert _checks(make_actor_mismatch_map("Zoe")).get("actor-attribution") == "ADVISORY"


def test_actor_attribution_matches_when_actors_agree() -> None:
    """No finding when the flow opens with the use case's declared actor."""
    assert "actor-attribution" not in _checks(make_actor_mismatch_map("Andy"))


def test_actor_markdown_is_not_a_false_positive() -> None:
    """Finding 4: `**Andy**` (bold) must match `Andy`."""
    assert "actor-attribution" not in _checks(make_actor_variant_map("**Andy**", "Andy"))


def test_compound_actor_matches_any_alternative() -> None:
    """Finding 4: a compound Actor cell 'Admin or Manager' matches an opener of either."""
    assert "actor-attribution" not in _checks(make_actor_variant_map("Admin or Manager", "Admin"))


def test_background_trigger_opener_is_skipped() -> None:
    """Finding 3: with a Roles table, an opener that is not a defined Role (a Scheduler / webhook)
    is a background trigger, not an actor mismatch — skipped."""
    assert "actor-attribution" not in _checks(make_actor_variant_map("Andy", "Scheduler", roles=True))


def test_backward_why_ref_is_still_blocking() -> None:
    """The why-ref checks have no false positives, so they stay blocking contradictions."""
    checks = _checks(make_backward_whyref_map())
    assert checks.get("backward-why-ref") == "CONTRADICTION", checks
    code, out = run_audit(make_backward_whyref_map())
    assert code == 1 and "AUDIT FAILED" in out, out


def test_read_never_created_is_advisory_not_blocking() -> None:
    checks = _checks(make_read_never_created_map())
    assert checks.get("read-never-created") == "ADVISORY", checks
    code, _ = run_audit(make_read_never_created_map())
    assert code == 0, "an advisory alone must not block"


def test_whyless_nonfirst_step_warns() -> None:
    checks = _checks(make_whyless_map())
    assert checks.get("why-less-step") == "WARNING", checks


# --- L2 worklist ----------------------------------------------------------------
def test_l2_worklist_lists_security_surfaces_and_enforces_edges() -> None:
    items = l2(make_l2_map())
    claims = " ".join(w.claim for w in items)
    assert "Auth surface" in claims, claims
    assert "enforces" in claims, claims
    anchors = [w.anchor for w in items]
    assert "auth.py#L10" in anchors and "gate.py#L5" in anchors, anchors


def test_l2_worklist_grounds_external_dep_edges() -> None:
    """A `C→D` edge into an external dep is grounded regardless of verb — the system-boundary
    data-flow claim (`emits` into a `datastore`), carrying its call site."""
    items = l2(make_l2_dep_map())
    claims = [w.claim for w in items]
    assert "C1 emits D1" in claims, claims
    assert "audit_repo.py#L8" in [w.anchor for w in items], items


def test_l2_worklist_skips_explicit_library_deps() -> None:
    """A `C→D` edge into a dep EXPLICITLY tagged `library` is skipped — a false 'uses <lib>' is benign
    and that bucket is the high-count one the Context view folds away."""
    claims = " ".join(w.claim for w in l2(make_l2_dep_map()))
    assert "D2" not in claims, claims


def test_l2_worklist_grounds_untagged_dep_by_default() -> None:
    """Fail-safe: ONLY an explicit fold-tag skips a dep. D3 has no `Kind` cell (inference would call it
    'library'), yet its incoming edge is still grounded — an unrecognised external system must not slip
    through, which is exactly how the audit→Elastic edge survived."""
    claims = [w.claim for w in l2(make_l2_dep_map())]
    assert "C1 writes D3" in claims, claims


def test_l2_worklist_ranks_security_before_dep_edges() -> None:
    """Security (`enforces`) claims outrank external-dep data-flow claims in the worklist order."""
    claims = [w.claim for w in l2(make_l2_dep_map())]
    assert claims.index("C1 enforces C2") < claims.index("C1 emits D1"), claims


def test_l2_worklist_grounds_entity_ownership_edges() -> None:
    """A `C→E` ownership edge is grounded — a wrong persists/writes/reads mis-wires the
    subsystem→subdomain bridge."""
    claims = [w.claim for w in l2(make_l2_dep_map())]
    assert "C1 persists E1" in claims, claims


def test_l2_worklist_grounds_remaining_component_edges() -> None:
    """The broadened worklist grounds the WHOLE backbone — a plain `C→C` `calls` edge is on it too."""
    claims = [w.claim for w in l2(make_l2_dep_map())]
    assert "C1 calls C3" in claims, claims


def test_l2_worklist_ranks_backbone_tiers() -> None:
    """Ranking holds across every tier: security < external-dep < entity-ownership < remaining."""
    claims = [w.claim for w in l2(make_l2_dep_map())]
    order = [claims.index(c) for c in
             ("C1 enforces C2", "C1 emits D1", "C1 persists E1", "C1 calls C3")]
    assert order == sorted(order), claims


def test_l2_worklist_dedupes_by_claim() -> None:
    """G4: a duplicated edge row yields exactly ONE worklist claim — the first occurrence, its anchor
    kept — so the skeptic fan-out count is deterministic (no downstream ad-hoc collapse)."""
    items = [w for w in l2(make_duplicated_edge_map())
             if w.claim == "C1 emits D1"]
    assert len(items) == 1, items
    assert items[0].anchor == "audit_repo.py#L8", items


def test_l2_worklist_claims_are_self_describing() -> None:
    """G1: each edge item's `detail` carries both endpoints' names + source files, so a fresh-context
    skeptic given only the item can locate the code with NO map file. The short claim (`C1 enforces
    C2`) stays the stable key."""
    items = {w.claim: w for w in l2(make_described_map())}
    d = items["C1 enforces C2"].detail
    assert d is not None, items
    assert "C1 = AuthGate" in d and "src/auth/gate.py#L10" in d, d
    assert "C2 = PolicyStore" in d and "src/policy.py#L5" in d, d
    e = items["C2 persists E1"].detail
    assert e is not None and "E1 = Order" in e and "src/order.py#L1" in e, e
    dep = items["C1 emits D1"].detail
    assert dep is not None and "D1 = Elastic" in dep, dep


def test_l2_worklist_detail_reaches_the_cli_output() -> None:
    """The self-describing detail is printed (a `who:` line), so an agent driving the CLI — not the
    Python API — can hand a skeptic a claim it can resolve without the map."""
    code, out = run_audit(make_described_map())
    assert code == 0, out
    assert "who: From: C1 = AuthGate (src/auth/gate.py#L10)" in out, out


# --- built-in runner ------------------------------------------------------------
def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run())
