#!/usr/bin/env python3
"""Tests for `coyodex context` — the evidence bundle handed to a skeptic.

A skeptic spends its run fetching what this verb fetches once, and every file it opens joins a
context that every later turn re-reads. Measured across eight skeptic agents on one build:
52-62% of each one's bill was re-reading its own accumulated context, against 12-18% for
everything it wrote.

The bundle must never make a fault invisible. The two that matter are pinned first: a missing file
is a `false` verdict and must be shouted, and the bundle must say of itself that it is a starting
point, or a skeptic settles claims on a mechanical slice that cannot know what they turn on.

Run either way (needs an editable install: `make deps`):
    python3 tests/test_context.py
    pytest tests/test_context.py
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from coyodex import context
from coyodex.model import load_model


def make_map(tmp: Path) -> Path:
    """A map with one component, so a claim naming C1 has a record to quote."""
    body = {
        "format": "coyodex-map", "title": "t", "goal": "g", "commit": "abc1234",
        "components": [{"id": "C1", "name": "Gate", "purpose": "refuses a caller with no role",
                        "source": "src/gate.py:3"}],
    }
    p = tmp / "project-map.json"
    p.write_text(json.dumps(body), encoding="utf-8")
    return p


def make_repo(tmp: Path) -> Path:
    repo = tmp / "repo"
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "gate.py").write_text(
        "\n".join(f"line {n}" for n in range(1, 41)) + "\n", encoding="utf-8")
    return repo


def make_claims(tmp: Path, claims: list[dict]) -> Path:
    p = tmp / "claims.json"
    p.write_text(json.dumps({"schema": "coyodex-claims/v1", "theme": "backbone",
                             "claims": claims}), encoding="utf-8")
    return p


def run(tmp: Path, claims: list[dict], lines: int = 20) -> str:
    out = tmp / "bundle.md"
    code = context.main(["--map", str(make_map(tmp)), "--repo", str(make_repo(tmp)),
                         "--claims", str(make_claims(tmp, claims)),
                         "--out", str(out), "--lines", str(lines)])
    assert code == 0
    return out.read_text(encoding="utf-8")


def test_a_missing_file_is_shouted_not_quietly_skipped() -> None:
    """The skeptic contract calls an anchor whose file is absent `false`, not drift. A bundle that
    omitted it would put back the failure the contract fix removed: 24 such anchors were confirmed
    by eight skeptics out of eight."""
    with tempfile.TemporaryDirectory() as td:
        text = run(Path(td), [{"claim": "C1 refuses", "anchor": "src/gate_nonexistent.py:5"}])
        assert "IS NOT IN THE REPO" in text
        assert "src/gate_nonexistent.py" in text
        assert "`false`" in text
        assert "1 anchor(s) in this batch name a file that is not in the repo" in text


def test_the_bundle_says_it_is_a_starting_point() -> None:
    """It is a mechanical slice and cannot know what a claim really turns on. Without saying so it
    invites exactly the fabricated confirmation the contract forbids."""
    with tempfile.TemporaryDirectory() as td:
        text = run(Path(td), [{"claim": "C1 refuses", "anchor": "src/gate.py:10"}])
        assert "STARTING POINT" in text
        assert "fabricated confirmation" in text


def test_the_code_around_the_anchor_is_quoted_with_the_claim_line_marked() -> None:
    with tempfile.TemporaryDirectory() as td:
        text = run(Path(td), [{"claim": "C1 refuses", "anchor": "src/gate.py:20"}], lines=3)
        assert "line 17" in text and "line 23" in text
        assert "line 16" not in text and "line 24" not in text
        assert ">  20  line 20" in text or "> 20  line 20" in text


def test_the_map_record_of_every_id_the_claim_names_is_included() -> None:
    with tempfile.TemporaryDirectory() as td:
        text = run(Path(td), [{"claim": "C1 refuses a caller", "anchor": "src/gate.py:3"}])
        assert "refuses a caller with no role" in text, "C1's stored purpose"


def test_an_id_the_map_does_not_hold_is_skipped_not_faked() -> None:
    with tempfile.TemporaryDirectory() as td:
        text = run(Path(td), [{"claim": "C1 calls C99", "anchor": "src/gate.py:3"}])
        assert "C99" in text, "the claim text still names it"
        assert '"C99"' not in text, "but no record is invented for it"


def test_a_line_past_the_end_of_a_real_file_says_so() -> None:
    with tempfile.TemporaryDirectory() as td:
        text = run(Path(td), [{"claim": "C1 refuses", "anchor": "src/gate.py:900"}])
        assert "past its end" in text
        # The header paragraph always explains the missing-file rule; what must be absent is the
        # per-claim shout and the batch tally.
        assert "**THE FILE" not in text, "the file exists; only the line is wrong"
        assert "name a file that is not in the repo" not in text


def test_an_anchor_that_is_not_a_path_line_says_so() -> None:
    with tempfile.TemporaryDirectory() as td:
        text = run(Path(td), [{"claim": "C1 refuses", "anchor": "somewhere in the gate"}])
        assert "not a `path:line`" in text


def test_the_slice_is_clamped_at_the_file_edges() -> None:
    with tempfile.TemporaryDirectory() as td:
        text = run(Path(td), [{"claim": "C1 refuses", "anchor": "src/gate.py:2"}], lines=20)
        assert "line 1" in text
        assert " 0  " not in text


@pytest.mark.parametrize("claim,expected", [
    ("C120 calls C241", ["C120", "C241"]),
    ("Rule 'x' is enforced at a.py:1", []),
    ("C1 and C1 again", ["C1"]),
])
def test_ids_are_read_from_the_claim_in_order_without_repeats(claim: str,
                                                              expected: list[str]) -> None:
    assert context.ids_in(claim) == expected


def test_every_claim_in_the_batch_gets_an_entry() -> None:
    with tempfile.TemporaryDirectory() as td:
        text = run(Path(td), [{"claim": f"C1 does {n}", "anchor": "src/gate.py:3"}
                              for n in range(5)])
        assert text.count("## Claim ") == 5


def test_a_claims_file_with_no_claims_list_is_refused(capsys) -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        bad = tmp / "c.json"
        bad.write_text(json.dumps({"schema": "x"}), encoding="utf-8")
        code = context.main(["--map", str(make_map(tmp)), "--repo", str(make_repo(tmp)),
                             "--claims", str(bad)])
        assert code == 2
        assert "no `claims` list" in capsys.readouterr().err


def test_it_writes_nothing_into_the_map() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        map_path = make_map(tmp)
        before = map_path.read_text(encoding="utf-8")
        run(tmp, [{"claim": "C1 refuses", "anchor": "src/gate.py:3"}])
        assert map_path.read_text(encoding="utf-8") == before


def test_the_bundle_is_deterministic() -> None:
    """No model, no clock, no randomness: two runs must be byte-identical, or a before/after
    comparison measures the bundler instead of the change."""
    with tempfile.TemporaryDirectory() as td:
        claims = [{"claim": "C1 refuses", "anchor": "src/gate.py:12"}]
        assert run(Path(td), claims) == run(Path(td), claims)


def test_code_slice_reports_its_own_status() -> None:
    """The status is returned rather than folded into prose, because `no-file` is a verdict the
    skeptic owes and not a gap in this file's output."""
    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(Path(td))
        assert code_status(repo, "src/gate.py:10") == "ok"
        assert code_status(repo, "src/missing.py:10") == "no-file"
        assert code_status(repo, "src/gate.py:999") == "no-line"
        assert code_status(repo, "not an anchor at all") == "not-an-anchor"


def code_status(repo: Path, anchor: str) -> str:
    return context.code_slice(repo, anchor, 5)[0]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
