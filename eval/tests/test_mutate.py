#!/usr/bin/env python3
"""Tests for `coyodex_eval.mutate` — the planted-falsehood harness.

The harness measures a skeptic's RECALL, so its own correctness is load-bearing in an unusual way:
a mutation that is not actually false makes a skeptic look bad for being right, and a mutation that
is false in an EASIER way than its label claims makes a weak skeptic look strong. The second is the
one that already happened — see `test_a_drifted_anchor_lands_on_a_real_line`.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from coyodex_eval import mutate


def _batch(anchor: str = "src/a.py:20", stmt: str | None = None, n: int = 8) -> dict:
    """`n` claims, because `plant` mutates DISTINCT claims — one shape per claim. A single-claim
    batch silently plants only the first shape, which made the first version of the swapped-actor
    test fail for a reason that had nothing to do with swapping actors."""
    stmt = stmt or ("Only the owner may delete it; the asker is told the item was not found, "
                    "never that it exists but is out of their reach.")
    return {"schema": "coyodex/theme-batch/v1", "theme": "rule",
            "claims": [{"claim": f"Rule '{stmt}' is enforced at {anchor} — decides case {i}",
                        "anchor": anchor, "detail": f"In: X (C{i})", "why_risky": "r"}
                       for i in range(n)]}


def test_a_drifted_anchor_lands_on_a_real_line():
    """The first version offset the line by a constant, which put every drift PAST end-of-file. That
    is a ghost LINE — the same easy shape as `ghost_file` wearing the hard shape's name — and it
    would have made the whole experiment measure the wrong thing: the case that matters is a line
    that EXISTS and simply is not the one enforcing the rule."""
    with tempfile.TemporaryDirectory() as d:
        repo = Path(d)
        (repo / "src").mkdir()
        (repo / "src" / "a.py").write_text("\n".join(f"line_{i} = {i}" for i in range(1, 201)))
        run = mutate.plant(_batch(), n=1, seed=1, repo=repo)
        drift = [p for p in run.planted if p.shape == "drifted_anchor"]
        assert drift, "no drift planted"
        path, _, line = drift[0].mutated_anchor.rpartition(":")
        n = len((repo / path).read_text().splitlines())
        assert 1 <= int(line) <= n, f"{drift[0].mutated_anchor} is past EOF ({n} lines)"
        assert drift[0].mutated_anchor != drift[0].original_anchor


def test_a_drift_is_not_planted_without_the_repo():
    """Silently degrading to a constant offset would reintroduce the ghost-line bug. No repo, no
    drift — the shape is skipped and the caller sees a smaller planted count."""
    run = mutate.plant(_batch(), n=1, seed=1, repo=None)
    assert not [p for p in run.planted if p.shape == "drifted_anchor"]


def test_a_negated_clause_keeps_the_first_half_true():
    """The valuable catch: half the sentence still matches the code, so a skeptic reading for the
    gist confirms it. If the mutation flipped the whole statement it would be no harder than
    `swapped_actor` and the two shapes would measure the same thing."""
    run = mutate.plant(_batch(), n=8, seed=3, repo=None)
    neg = [p for p in run.planted if p.shape == "negated_clause"]
    assert neg, "no negated clause planted"
    o, m = neg[0].original_claim, neg[0].mutated_claim
    head_len = min(len(o), len(m))
    first_diff = next((i for i in range(head_len) if o[i] != m[i]), head_len)
    assert first_diff > len(o) // 3, (
        "the change landed in the FIRST clause — the shape is supposed to leave it intact")


def test_a_swapped_actor_changes_the_access_sense():
    run = mutate.plant(_batch(), n=8, seed=3, repo=None)
    sw = [p for p in run.planted if p.shape == "swapped_actor"]
    assert sw and sw[0].mutated_claim != sw[0].original_claim


def test_every_planted_claim_actually_differs_from_the_original():
    """A no-op mutation would be scored as a falsehood the skeptic 'missed' while being true."""
    with tempfile.TemporaryDirectory() as d:
        repo = Path(d)
        (repo / "src").mkdir()
        (repo / "src" / "a.py").write_text("\n".join(f"x{i} = {i}" for i in range(1, 201)))
        run = mutate.plant(_batch(), n=4, seed=5, repo=repo)
        for p in run.planted:
            assert (p.mutated_claim != p.original_claim
                    or p.mutated_anchor != p.original_anchor), f"{p.shape} changed nothing"


def test_unverifiable_counts_as_caught_and_only_a_confirmation_is_a_miss():
    """The claim is false; declining to confirm it is the honest outcome the three-way vocabulary
    exists for. Scoring `unverifiable` as a miss would punish exactly the behaviour the contract
    asks for, and would make the experiment reward overconfident refutation."""
    key = [{"index": 0, "shape": "ghost_file", "original_claim": "o", "original_anchor": "a",
            "mutated_claim": "MUT", "mutated_anchor": "b"}]
    assert mutate.score(key, [{"claim": "MUT", "grounded": "unverifiable"}])["caught"] == 1
    assert mutate.score(key, [{"claim": "MUT", "grounded": False}])["caught"] == 1
    got = mutate.score(key, [{"claim": "MUT", "grounded": True}])
    assert got["caught"] == 0 and got["misses"]


def test_a_planted_claim_with_no_verdict_is_reported_not_counted_as_caught():
    """A skeptic that returns 30 rows for 40 claims must not score better than one that answers
    every claim — silence is not detection."""
    key = [{"index": 0, "shape": "ghost_file", "original_claim": "o", "original_anchor": "a",
            "mutated_claim": "MUT", "mutated_anchor": "b"}]
    got = mutate.score(key, [{"claim": "something else", "grounded": True}])
    assert got["caught"] == 0 and got["unvoted"] == 1


def test_a_drift_is_scored_on_the_evidence_not_the_verdict():
    """Getting this wrong invalidated the first run of this experiment. The skeptic contract says a
    drifted anchor does NOT refute a true relationship — confirm the claim, return the line you
    actually found, and let the drift check reconcile it. Scoring drift as a refutation marked four
    skeptics 0/3 for obeying their instructions, and would have been published as evidence that they
    were weak. All four had returned the exact original line in `evidence`."""
    key = [{"index": 0, "shape": "drifted_anchor", "original_claim": "o",
            "original_anchor": "src/a.py:42", "mutated_claim": "MUT",
            "mutated_anchor": "src/a.py:200"}]
    obedient = [{"claim": "MUT", "grounded": True, "evidence": "src/a.py:42"}]
    got = mutate.score(key, obedient)
    assert got["caught"] == 1, "confirming with the corrected line is the CONTRACT's answer"
    assert got["per_shape"]["drifted_anchor"].get("exact") == 1
    lazy = [{"claim": "MUT", "grounded": True, "evidence": "src/a.py:200"}]
    assert mutate.score(key, lazy)["caught"] == 0, \
        "repeating the anchor it was handed means it never looked"
