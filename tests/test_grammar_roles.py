#!/usr/bin/env python3
"""Tests for the WS2 backbone-verb → ROLE vocabulary in `coyodex.grammar`: `edge_role` (each verb
family → its role, generic/unknown → None) and `dep_roles` (the derived role SET of a dependency).

Run either way (needs an editable install: `make deps`):
    python3 tests/test_grammar_roles.py
    pytest tests/test_grammar_roles.py
"""
from __future__ import annotations

from coyodex import grammar
from coyodex.grammar import dep_roles, edge_role


def test_edge_role_maps_each_family_to_its_role():
    # datastore: persist + write + read families (a query/fetch IS a store read)
    for v in ("persists", "upserts", "stores", "writes", "updates", "reads", "queries", "fetches", "gets"):
        assert edge_role(v) == "datastore", v
    # messaging: emit family
    for v in ("emits", "publishes", "dispatches", "broadcasts", "enqueues"):
        assert edge_role(v) == "messaging", v
    # service: call family ONLY (NOT queries/fetches)
    for v in ("calls", "requests", "invokes"):
        assert edge_role(v) == "service", v
    # security: encrypt family
    for v in ("encrypts", "decrypts"):
        assert edge_role(v) == "security", v


def test_queries_and_fetches_are_datastore_not_service():
    # review finding #2: "queries the database" / "fetches the record" are store reads, not calls.
    assert edge_role("queries") == "datastore"
    assert edge_role("fetches") == "datastore"


def test_generic_and_unknown_verbs_have_no_role():
    for v in grammar.GENERIC_VERBS:
        assert edge_role(v) is None, v
    assert edge_role("uses") is None
    assert edge_role("frobnicates") is None       # unrecognized → None (nudged on a C→D edge)
    assert edge_role("") is None


def test_edge_role_is_case_and_whitespace_insensitive():
    assert edge_role("  Publishes ") == "messaging"
    assert edge_role("READS") == "datastore"


def test_dep_roles_unions_incoming_verbs():
    # the load-bearing case: Redis as bus AND store → both roles, from its two real verbs.
    assert dep_roles(["publishes", "writes"]) == {"messaging", "datastore"}


def test_dep_roles_drops_roleless_and_empty_is_empty():
    assert dep_roles(["uses", "reads"]) == {"datastore"}   # the generic verb contributes nothing
    assert dep_roles([]) == set()                           # no C→D edges → no role tag


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok {name}")
