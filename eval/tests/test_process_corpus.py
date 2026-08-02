#!/usr/bin/env python3
"""L3 corpus run — the scorecard against eight REAL build transcripts. OPT-IN, never a gate.

Run either way (needs an editable install: `make deps`):
    COYODEX_L3_CORPUS=1 python3 eval/tests/test_process_corpus.py
    COYODEX_L3_CORPUS=1 pytest eval/tests/test_process_corpus.py

**Why opt-in.** These transcripts live in `~/.claude/projects/`, outside the repo. They will not
exist on another machine or in CI, so every test here SKIPS cleanly when the files are absent and
the default suite never depends on them. `test_process_scorecard.py` carries the deterministic
logic tests that DO run everywhere.

**Why it exists anyway.** The detectors in `process_scorecard.py` were calibrated against these
eight files, and four separate false positives were found and fixed that way — a heredoc that
mentioned `coyodex anchor-drift` without running it, a `git add` that named `preindex.json` without
parsing it, a binary aliased to `$CX` that hid every invocation behind it, and a `reconcile.json`
produced by a generator script rather than a redirect. A synthetic test cannot find those, because
the author of the synthetic test is the author of the bug. What this file pins is that the numbers
those fixes produced do not silently change.

The corpus is 4 post-change builds (2026-07-29) and the 4 baseline builds of the same repos from
the night before. The comparison between them is the first real answer to 'did the method changes
land'.

**Still not a gate.** Even here, a moved number is a finding to look at, not a failure: these are
LLM builds and they vary. The assertions below pin only the facts that are structural — a value
that could not move without either the transcript or the detector changing.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from coyodex_eval.process_scorecard import Scorecard, diff, score_transcript

#: Set this to run the corpus. Absent, every test here skips.
ENV_FLAG = "COYODEX_L3_CORPUS"

PROJECTS = Path.home() / ".claude" / "projects"


@dataclass(frozen=True)
class Build:
    """One transcript in the corpus."""

    era: str          # "post" (after the method changes) | "base" (the night before)
    repo: str
    relative: str

    @property
    def path(self) -> Path:
        return PROJECTS / self.relative

    @property
    def label(self) -> str:
        return f"{self.era}/{self.repo}"


CORPUS: tuple[Build, ...] = (
    Build("post", "coyodex", "-Users-nitsanseniak-Projects-coyodex/"
                             "36b1b143-b7a4-4a04-89f5-40a9bf932746.jsonl"),
    Build("post", "argus", "-Users-nitsanseniak-Projects-argus/"
                           "07a8f4e9-54b6-4afb-b6c8-48ec987d3770.jsonl"),
    Build("post", "mcpolis", "-Users-nitsanseniak-mee6-repos-mcpolis/"
                             "fbc095e4-9edf-4935-af33-86dac6a6efdd.jsonl"),
    Build("post", "mee6", "-Users-nitsanseniak-mee6-repos-mee6/"
                          "a2d36839-9b29-4f58-b756-f2c501539063.jsonl"),
    Build("base", "coyodex", "-Users-nitsanseniak-Projects-coyodex/"
                             "25ff248b-c035-4499-a4ae-ff67f3d91142.jsonl"),
    Build("base", "argus", "-Users-nitsanseniak-Projects-argus/"
                           "01331ac9-0678-485d-8469-111aa21ea049.jsonl"),
    Build("base", "mcpolis", "-Users-nitsanseniak-mee6-repos-mcpolis/"
                             "24905cb7-69ab-4af9-afd8-84625554dfe3.jsonl"),
    Build("base", "mee6", "-Users-nitsanseniak-mee6-repos-mee6/"
                          "23e4e486-86cb-44b5-984c-988f634fbbd3.jsonl"),
    # The 2026-08-02 mcpolis build, added because an adversarial review of that day's detector
    # repairs found three of them producing ZERO delta across the eight transcripts above: no build
    # in the original corpus invokes `coyodex grounding` at all (assertion 13 scores 0/0 on every
    # one), none redirects a gate to a file and reads it back with the Read tool (assertions 9 and
    # 23's new path), and none runs `audit --batches` or `fix dedup-edge --to-reconcile`. The rule
    # "measure a repaired detector against the corpus BOTH ways" was being satisfied vacuously.
    # This build exercises all four, and is the negative case for assertion 10 — 0 idle polls
    # against the 36 the other eight carry between them.
    Build("0802", "mcpolis", "-Users-nitsanseniak-mee6-repos-mcpolis/"
                             "e2f11ef1-2ef5-4117-bad1-61235a661a97.jsonl"),
)


# --- builders -------------------------------------------------------------------------

def corpus_enabled() -> bool:
    return bool(os.environ.get(ENV_FLAG)) and all(b.path.is_file() for b in CORPUS)


def make_cards() -> dict[str, Scorecard]:
    """Every transcript scored, keyed by label. The one place the corpus is read."""
    return {b.label: score_transcript(b.path, label=b.label) for b in CORPUS}


def observed_of(cards: dict[str, Scorecard], label: str, aid: int) -> tuple[int, int]:
    a = cards[label].by_id()[aid]
    return a.observed, a.of


def era(cards: dict[str, Scorecard], name: str) -> list[Scorecard]:
    return [c for label, c in cards.items() if label.startswith(name + "/")]


def _skip() -> bool:
    if corpus_enabled():
        return False
    print(f"  (skipped — set {ENV_FLAG}=1 and have the transcripts under {PROJECTS})")
    return True


# --- the grouping assumption ----------------------------------------------------------

def test_every_transcript_groups_consistently():
    """The whole fan-out measurement rests on 'one message id == one API response'. Across all
    eight real transcripts no message id ever carried two different usage blocks. If this fails, a
    harness format change has invalidated assertion 3 and the number must not be trusted."""
    if _skip():
        return
    for label, card in make_cards().items():
        assert card.grouping_consistent, f"{label}: a message id carried two different usage blocks"


# --- the five answers established from these exact files ------------------------------

def test_the_preindex_read_command_was_adopted_after_the_method_change():
    """Assertion 1. All four POST-change builds ran `preindex --report`; none of the four baselines
    did. This is the cleanest adoption signal in the corpus."""
    if _skip():
        return
    cards = make_cards()
    for c in era(cards, "post"):
        assert c.by_id()[1].observed >= 1, f"{c.label}: no `preindex --report`"
    for c in era(cards, "base"):
        assert c.by_id()[1].observed == 0, f"{c.label}: baseline should predate the read command"


def test_hand_parsing_the_preindex_stopped_after_the_method_change():
    """Assertion 2. The baselines parsed `preindex.json` themselves — every single touch. The
    post-change builds did not hand-parse it once."""
    if _skip():
        return
    cards = make_cards()
    for c in era(cards, "post"):
        a = c.by_id()[2]
        assert a.observed == a.of, f"{c.label}: {a.of - a.observed} hand-parse(s) remain"
    for c in era(cards, "base"):
        a = c.by_id()[2]
        assert a.of > 0 and a.observed == 0, f"{c.label}: baseline should be all hand-parses"


def test_the_reconcile_command_went_from_never_used_to_used():
    """Assertion 7 — the headline class-2 defect, and the one this corpus can now show being fixed.

    Seven of the original eight builds produced a `reconcile.json` and ZERO produced it with
    `coyodex reconcile`; every one wrote it by hand or generated it with a script. That held across
    ten builds and is why the "~30 assignments" escape was deleted from method.md.

    The `0802` build is the first to reach for the command — twice, at turns 147 and 149. This test
    now pins BOTH halves, because a regression in either direction is the interesting event: the
    historical builds must keep reading 0 (the reader still sees what it saw), and at least one
    build must be using it (the fix stays reached)."""
    if _skip():
        return
    cards = make_cards()
    produced = used = 0
    for label, c in cards.items():
        a = c.by_id()[7]
        if label.startswith("0802/"):
            assert a.observed > 0, f"{label}: the command stopped being reached — regression"
        else:
            assert a.observed == 0, f"{label}: a historical build cannot have used it — reader bug"
        used += a.observed
        produced += a.of
    assert produced >= 7, f"only {produced} reconcile.json production(s) seen across the corpus"
    assert used >= 1, "no build in the corpus reaches `coyodex reconcile`"


def test_grounding_was_recorded_after_the_change_and_never_before():
    """Assertion 6. All four post-change builds recorded a `grounding` object; not one baseline
    did — including the baseline coyodex build, which had none at all."""
    if _skip():
        return
    cards = make_cards()
    for c in era(cards, "post"):
        assert c.by_id()[6].observed >= 1, f"{c.label}: no grounding record"
    for c in era(cards, "base"):
        assert c.by_id()[6].observed == 0, f"{c.label}: baseline recorded grounding unexpectedly"


def test_the_shape_only_anchor_drift_pass_was_reached_by_three_of_four_post_builds():
    """Assertion 4. Three of the four post-change builds ran `anchor-drift` with no `--verdicts`;
    mee6 did not. No baseline ran it at all — every baseline invocation passed `--verdicts`.

    This is one of the two numbers where the brief's expectation and the transcripts disagree: the
    brief said one of four. Each of the three is a real invocation, verified command by command —
    `.venv/bin/coyodex anchor-drift --map .coyodex/project-map.json` with no verdicts flag."""
    if _skip():
        return
    cards = make_cards()
    reached = [c.label for c in era(cards, "post") if c.by_id()[4].observed >= 1]
    assert len(reached) == 3, f"expected three post-change builds, got {reached}"
    assert all(c.by_id()[4].observed == 0 for c in era(cards, "base"))


def test_fan_outs_are_batched_in_seven_of_eight_builds():
    """Assertion 3 — THE HEADLINE, and the number that contradicts the brief outright.

    The expectation handed to this work was ZERO batched fan-outs across all eight transcripts:
    every fan-out one agent per turn. That is not what the files say. Seven of the eight builds
    contain at least one assistant message carrying two or more `Agent` calls; the eighth
    (base/coyodex) launched no agents at all, so it has no fan-out to batch.

    The prior measurement almost certainly counted JSONL RECORDS as turns. This harness writes one
    content block per record and stamps each with the time the tool EXECUTED, so a message that
    emitted ten `Agent` calls appears as ten records minutes apart with the results interleaved —
    which reads exactly like one agent per turn. What settles it: those records share one
    `message.id`, one `requestId` and one identical `usage` block, and there is exactly ONE
    `thinking` block among all ten. A model does not emit ten tool-calling responses of which nine
    contain no reasoning."""
    if _skip():
        return
    cards = make_cards()
    batched = {label: c.by_id()[3].observed for label, c in cards.items()}
    assert batched["base/coyodex"] == 0 and cards["base/coyodex"].by_id()[3].of == 0, (
        "base/coyodex is the serial build — no agents at all, so assertion 3 is n/a, not 0")
    others = {k: v for k, v in batched.items() if k != "base/coyodex"}
    assert all(v >= 1 for v in others.values()), f"expected batching everywhere else: {others}"


# --- the diff, which is what the scorecard is for -------------------------------------

def test_the_post_change_era_did_not_regress_on_the_adoption_assertions():
    """The four assertions the method change was ABOUT — 1, 2, 4, 6 — all move up, per repo, with
    no regression. This is the diff mode doing the job it exists for."""
    if _skip():
        return
    cards = make_cards()
    for repo in ("coyodex", "argus", "mcpolis", "mee6"):
        rows = {d.id: d for d in diff(cards[f"base/{repo}"], cards[f"post/{repo}"])}
        for aid in (1, 2, 6):
            assert rows[aid].direction in ("up", "flat", "new"), (
                f"{repo}: assertion {aid} moved {rows[aid].direction} "
                f"({rows[aid].before_counts} -> {rows[aid].after_counts})")


def test_the_corpus_prints_its_table():
    """Not an assertion — the corpus run's actual output. Kept as a test so `pytest -s` prints it
    and a reader gets the numbers without a separate script."""
    if _skip():
        return
    cards = make_cards()
    header = f"{'build':<15}{'turns':>6}" + "".join(f"{'A' + str(i):>9}" for i in range(1, 11))
    print("\n" + header)
    print("-" * len(header))
    for b in CORPUS:
        c = cards[b.label]
        print(f"{b.label:<15}{c.turns:>6}"
              + "".join(f"{str(a.observed) + '/' + str(a.of):>9}" for a in c.assertions))


def _main() -> int:
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {fn.__name__}\n  {str(exc)[:500]}\n")
    print(f"{len(fns) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
