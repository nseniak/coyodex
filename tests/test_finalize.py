#!/usr/bin/env python3
"""`coyodex finalize` — the pre-commit read.

The design point these pin: it is a CONVENIENCE WRAPPER, not an enforcement point. Nothing makes a
build run it, and `finalize | grep …` returns grep's status, so the value is (a) running `compare`
during the build at all — the check that caught a 103→19 security-table collapse every other gate
passed, and that nobody ran — and (b) writing a durable report a `> /dev/null` cannot erase.

Run either way: `python3 tests/test_finalize.py` or `pytest tests/test_finalize.py`.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from coyodex import finalize
from coyodex.model import FORMAT

#: A genuinely minimal VALID map — no entities, because a domain card carries its own blocking
#: requirements (meaning, fields, a real named type in its source) that have nothing to do with what
#: these tests are about. Two components and one C→C edge is the smallest thing that validates.
MAP = {
    "format": FORMAT,   # the real constant, so the fixture cannot drift from the loader
    "title": "T", "goal": "G",
    "roles": [{"id": "R1", "name": "A", "kind": "human", "wants": "x", "drives": "UC1"}],
    "use_cases": [{"id": "UC1", "name": "Do it", "actors": ["R1"]}],
    "happy_path": [{"id": "HP1", "title": "Do", "uc": "UC1"}],
    "components": [{"id": "C1", "name": "Front", "purpose": "takes the ask", "entry_point": "src/a.py:1"},
                   {"id": "C2", "name": "Back", "purpose": "answers it", "entry_point": "src/b.py:1"}],
    "edges": [{"src": "C1", "verb": "calls", "dst": "C2", "why": "to answer", "where": "src/a.py:2"}],
    "flows": [{"uc": "UC1", "title": "Do it",
               "steps": [{"n": 1, "src": "R1", "dst": "C1", "phrase": "asks"},
                         {"n": 2, "src": "C1", "dst": "C2", "phrase": "forwards", "where": "src/a.py:2"},
                         {"n": 3, "src": "C1", "dst": "R1", "phrase": "answers"}]}],
}


def make_git_repo() -> tuple[Path, Path]:
    """A repo with real git history. `finalize` reads no git state now (it compares nothing against a
    previous map — that is the developer-only retro's job), so this exists only to prove the command
    stays clean in a repo where a previous version of it used to materialise a baseline copy."""
    root, p = make_repo()
    subprocess.run(["git", "init", "-q", "."], cwd=root, check=True)
    subprocess.run(["git", "add", "-f", str(p.relative_to(root))], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "map"],
                   cwd=root, check=True)
    return root, p


def make_repo(broken: bool = False, components: int = 0) -> tuple[Path, Path]:
    root = Path(tempfile.mkdtemp())
    (root / "src").mkdir()
    (root / "src" / "a.py").write_text("def front():\n    return back()\n", encoding="utf-8")
    (root / "src" / "b.py").write_text("def back():\n    return 1\n", encoding="utf-8")
    (root / ".coyodex").mkdir()
    doc = json.loads(json.dumps(MAP))
    if components:
        # An edgeless map of N components: the isolated-component advisory lists every id, so a
        # truncation (or its absence) is observable.
        doc["components"] = [{"id": f"C{i}", "name": f"C{i}", "purpose": "p",
                              "entry_point": "src/a.py:1"} for i in range(1, components + 1)]
        doc["edges"] = []
        doc["flows"] = [{"uc": "UC1", "title": "Do it",
                         "steps": [{"n": 1, "src": "R1", "dst": "C1", "phrase": "asks"},
                                   {"n": 2, "src": "C1", "dst": "C2", "phrase": "f",
                                    "where": "src/a.py:2"},
                                   {"n": 3, "src": "C1", "dst": "R1", "phrase": "answers"}]}]
    if broken:
        doc["edges"][0]["dst"] = "C999"        # a dangling reference — a BLOCKING validate problem
    p = root / ".coyodex" / "project-map.json"
    p.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return root, p


def test_a_clean_map_exits_zero_and_writes_both_reports():
    root, p = make_repo()
    code = finalize.main([str(p), "--repo", str(root)])
    assert code == 0
    assert (root / ".coyodex" / "finalize-report.json").is_file()
    assert (root / ".coyodex" / "finalize-report.md").is_file()


def test_a_blocking_problem_exits_one_and_is_recorded_as_blocking():
    """Exit 1 means exactly what validate/audit already block on — nothing more."""
    root, p = make_repo(broken=True)
    code = finalize.main([str(p), "--repo", str(root)])
    assert code == 1
    report = json.loads((root / ".coyodex" / "finalize-report.json").read_text(encoding="utf-8"))
    assert report["verdict"] == "BLOCKED"
    assert report["blocking_total"] >= 1
    assert any("C999" in b for leg in report["legs"] for b in leg["blocking"])


def test_a_leg_that_did_not_run_can_never_produce_a_verdict_of_clean():
    """The defect this command shipped in its first cut, and the whole reason `Leg.status` exists.

    A leg that did not run contributed 0 blocking and 0 advisory, so a broken map with a typo'd
    `--repo` reported **Verdict: CLEAN**, exit 0 — a report testifying that a gate passed when the gate
    never ran. Worse than no report at all."""
    root, p = make_repo(broken=True)                 # a dangling reference: validate exits 1 on this
    code = finalize.main([str(p), "--repo", "/nonexistent-dir-for-this-test"])
    r = json.loads((root / ".coyodex" / "finalize-report.json").read_text(encoding="utf-8"))
    assert r["verdict"] == "INCOMPLETE", r["verdict"]
    assert code != 0, "a run that does not know whether the map is clean must not exit 0"
    assert any(l["status"] == "failed" for l in r["legs"])
    md = (root / ".coyodex" / "finalize-report.md").read_text(encoding="utf-8")
    verdict_line = next(ln for ln in md.splitlines() if ln.startswith("**Verdict:"))
    assert "CLEAN" not in verdict_line, verdict_line
    assert "their silence is not a pass" in md


def test_the_report_is_byte_identical_across_identical_runs():
    """Non-determinism in a pre-commit report is a defect: a build cannot tell a real change from
    noise, and a diff of the committed report becomes unreadable."""
    root, p = make_repo()
    finalize.main([str(p), "--repo", str(root)])
    first = (root / ".coyodex" / "finalize-report.json").read_text(encoding="utf-8")
    finalize.main([str(p), "--repo", str(root)])
    assert (root / ".coyodex" / "finalize-report.json").read_text(encoding="utf-8") == first


def test_it_leaves_no_scratch_files_beside_the_map():
    """An earlier version materialised a ~800 KB copy of the previous map next to the real one and
    deleted it only on the success path. Nothing is materialised now; this holds that line."""
    root, p = make_git_repo()
    finalize.main([str(p), "--repo", str(root)])
    strays = [f.name for f in (root / ".coyodex").iterdir()
              if f.name.startswith(f".{finalize.REPORT_STEM}")]
    assert strays == [], strays


def test_a_crash_mid_run_leaves_no_scratch_behind():
    """A malformed `--verdicts` file reaches the drift leg and raises. Nothing temporary may survive."""
    root, p = make_git_repo()
    boom = root / ".coyodex" / "not-json.json"
    boom.write_text("{{{ not json", encoding="utf-8")
    try:
        finalize.main([str(p), "--repo", str(root), "--verdicts", str(boom)])
    except Exception:
        pass
    strays = [f.name for f in (root / ".coyodex").iterdir()
              if f.name.startswith(f".{finalize.REPORT_STEM}")]
    assert strays == [], strays


def test_a_missing_map_and_a_missing_verdicts_file_fail_before_any_leg_runs():
    root, p = make_repo()
    assert finalize.main([str(root / ".coyodex" / "nope.json")]) == 1
    assert finalize.main([str(p), "--repo", str(root), "--verdicts", str(root / "nope.json")]) == 1


def test_the_report_carries_whole_lists_on_a_map_big_enough_to_truncate():
    """The previous version asserted `"more" not in … or "+" not in …` on a 2-component map — both
    disjuncts trivially true, and it passed with whole-list mode removed. This builds a map with 30
    isolated components, well past the 8-id inline limit, and asserts the ids are all present."""
    root, p = make_repo(components=30)
    finalize.main([str(p), "--repo", str(root)])
    text = (root / ".coyodex" / "finalize-report.md").read_text(encoding="utf-8")
    isolated = [ln for ln in text.splitlines() if "carry no backbone edge" in ln]
    assert isolated, "expected the isolated-component advisory on a 30-component edgeless map"
    assert "more" not in isolated[0], isolated[0]
    assert "C30" in isolated[0], "the last id must be present, not elided"


def test_the_help_says_it_is_not_an_enforcement_point():
    """If the docs ever start promising enforcement, the promise is false — the exit status is lost to
    any pipeline. Pinned so the claim cannot drift back."""
    r = subprocess.run([sys.executable, "-m", "coyodex.cli", "finalize", "--help"],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert "not an enforcement point" in r.stdout
    assert "never gating" in r.stdout


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all finalize tests passed")


def test_the_report_records_the_maps_hash_so_a_stale_one_is_detectable():
    """A crash writes no report, so the PREVIOUS run's file survives — and the method tells the build to
    read the file. The hash is how a reader tells this map's result from another's."""
    import hashlib
    root, p = make_repo()
    finalize.main([str(p), "--repo", str(root)])
    r = json.loads((root / ".coyodex" / "finalize-report.json").read_text(encoding="utf-8"))
    assert r["map_sha256"] == hashlib.sha256(p.read_bytes()).hexdigest()
    assert r["map_sha256"] in (root / ".coyodex" / "finalize-report.md").read_text(encoding="utf-8")


def test_a_grounding_record_pinned_to_a_stale_worklist_is_flagged():
    """A live build shipped `418 of 418 challenged` on a map whose worklist held 415 and quoted the
    418 in its commit as fact. `validate` cannot see it — it blocks only `challenged > total`, and a
    stale pin is self-consistent."""
    from coyodex.finalize import _stale_grounding_pin
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "m.json"
        p.write_text(json.dumps({"format": FORMAT, "title": "T", "goal": "g",
                                 "grounding": {"claims_total": 418, "claims_challenged": 418}}),
                     encoding="utf-8")
        msg = _stale_grounding_pin(p, [f"claim {i}" for i in range(415)])
        assert msg and "418" in msg and "415" in msg
        # Agreeing counts are NOT a pass without a digest: a 1-for-1 rewrite leaves the count
        # untouched, so this branch says the record cannot be checked rather than that it is fine.
        msg2 = _stale_grounding_pin(p, [f"c{i}" for i in range(418)])
        assert msg2 and "no `live_claims_digest`" in msg2, msg2


def test_a_map_with_no_grounding_record_is_not_flagged():
    from coyodex.finalize import _stale_grounding_pin
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "m.json"
        p.write_text(json.dumps({"format": FORMAT, "title": "T", "goal": "g"}), encoding="utf-8")
        assert _stale_grounding_pin(p, [f"c{i}" for i in range(415)]) is None


# ── the commit message's two other lies ──────────────────────────────────────────────────────────

def test_the_gate_block_states_the_shape_from_the_map_it_hashes():
    """A live commit claimed "416 backbone edges … 33 flows/sub-flows" for a map holding 365 and 36.
    Both numbers had been true earlier in the build; `fix dedup-edge` then dropped 49 duplicate
    occurrences. Hand-copied shape numbers describe whatever the author last looked at."""
    root, p = make_repo(components=4)
    report = finalize.build_report(p, root, [])
    block = finalize.gate_block(report, report.map_sha256)
    doc = json.loads(p.read_text())
    assert f"{len(doc['components'])} components" in block
    assert f"{len(doc['edges'])} edges" in block


def test_the_gate_block_states_grounding_from_the_map_not_from_memory():
    """A live commit said "all 446 L2 claims challenged" beside a gate block reading
    `challenged 440 of 444`. Both were minutes apart in one build; the durable one was the
    flattering one."""
    root, p = make_repo()
    doc = json.loads(p.read_text())
    doc["grounding"] = {"claims_total": 444, "claims_challenged": 440, "claims_confirmed": 430,
                        "claims_refuted": 5, "claims_unverifiable": 5}
    p.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    report = finalize.build_report(p, root, [])
    block = finalize.gate_block(report, report.map_sha256)
    assert "440 of 444" in block, block


def test_the_gate_block_says_so_when_the_map_carries_no_grounding_record():
    """Silence would read as "not applicable" rather than "nobody challenged anything"."""
    root, p = make_repo()
    report = finalize.build_report(p, root, [])
    assert "NO RECORD" in finalize.gate_block(report, report.map_sha256)


def test_an_unreadable_map_says_so_instead_of_omitting_the_shape():
    """A gate block that silently drops the Shape and Grounding lines sends the author back to
    hand-writing the numbers, which is the defect those lines exist to remove."""
    root, p = make_repo()
    report = finalize.build_report(p, root, [])
    p.write_text("{truncated", encoding="utf-8")          # as a concurrent write would leave it
    block = finalize.gate_block(report, report.map_sha256)
    assert "Shape: UNAVAILABLE" in block and "Grounding: UNAVAILABLE" in block


def test_a_recorded_delta_makes_the_pin_advisory_go_quiet():
    """The escape that did not exist. All three documented ways out were closed: the pinned record
    raised this advisory, re-running against a fresh worklist was REFUSED, and explaining it in
    `note` changed nothing. `grounding write --map` records the delta and a digest of the live
    claim set, and that is what the gate now reads."""
    from coyodex.finalize import _stale_grounding_pin
    from coyodex.grounding import live_claims_digest
    live = [f"claim {i}" for i in range(444)]
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "m.json"
        p.write_text(json.dumps({"format": FORMAT, "title": "T", "goal": "g", "grounding": {
            "claims_total": 446, "claims_challenged": 446, "claims_superseded": 6,
            "claims_added_since": 4, "live_claims_digest": live_claims_digest(live)}}),
            encoding="utf-8")
        assert _stale_grounding_pin(p, live) is None


def test_the_digest_catches_a_one_for_one_rewrite_that_the_counts_cannot():
    """The reason the gate is a digest and not arithmetic. Replace k claims with k others and every
    size-based check still closes — and a reconcile that rewrites a claim IS 1-for-1 by
    construction; 4 of 6 superseded claims on the build this came from were exactly that shape."""
    from coyodex.finalize import _stale_grounding_pin
    from coyodex.grounding import live_claims_digest
    # claims_total EQUALS the live count on purpose: with 446-vs-444 the count check would fire
    # too, and the test would not distinguish the branches. Here only the digest can catch it.
    live = [f"claim {i}" for i in range(444)]
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "m.json"
        p.write_text(json.dumps({"format": FORMAT, "title": "T", "goal": "g", "grounding": {
            "claims_total": 444, "claims_challenged": 444, "claims_superseded": 6,
            "claims_added_since": 6, "live_claims_digest": live_claims_digest(live)}}),
            encoding="utf-8")
        swapped = live[:-1] + ["a claim authored after the record was written"]
        assert len(swapped) == len(live), "the count must be unchanged, or this proves nothing"
        msg = _stale_grounding_pin(p, swapped)
        assert msg and "live_claims_digest" in msg, msg


def make_verdicts_file(tmp: str, claims: list[str]) -> Path:
    """A verdicts file whose claims are the PINNED set — which is what `grounding write`'s two
    refusals guarantee, and what makes the delta counts recomputable."""
    p = Path(tmp) / "verdicts.json"
    p.write_text(json.dumps({"grounding": [
        {"claim": c, "grounded": True, "evidence": "f.py:1"} for c in claims]}), encoding="utf-8")
    return p


def make_grounding_map(tmp: str, live: list[str], **grounding: object) -> Path:
    from coyodex.grounding import live_claims_digest
    p = Path(tmp) / "m.json"
    rec = {"claims_total": len(live), "claims_challenged": len(live),
           "live_claims_digest": live_claims_digest(live)}
    rec.update(grounding)
    p.write_text(json.dumps({"format": FORMAT, "title": "T", "goal": "g", "grounding": rec}),
                 encoding="utf-8")
    return p


def test_a_fabricated_delta_count_is_caught_when_the_verdicts_are_present():
    """The digest proves the record describes THIS map. It says nothing about whether the two delta
    counts are true — a valid digest and two invented numbers coexist happily, which is a poor
    property for the fields whose only job is honesty."""
    from coyodex.finalize import _stale_grounding_pin
    with tempfile.TemporaryDirectory() as tmp:
        live = ["kept", "added-since-the-pin"]
        pinned = ["kept", "reconciled-away"]
        p = make_grounding_map(tmp, live, claims_superseded=0, claims_added_since=0)
        v = make_verdicts_file(tmp, pinned)
        assert _stale_grounding_pin(p, live) is None, "without verdicts there is nothing to check"
        msg = _stale_grounding_pin(p, live, [v])
        # Only the LOWER bound on superseded fires here. `claims_added_since: 0` sits BELOW the
        # upper bound, which a partial verdict set legitimately permits — only a count ABOVE what
        # the verdicts leave room for is provably wrong.
        assert msg and "already name 1 pinned claim(s)" in msg, msg
        over = make_grounding_map(tmp, live, claims_superseded=1, claims_added_since=9)
        msg2 = _stale_grounding_pin(over, live, [v])
        assert msg2 and "at most 1 live claim(s) can be new" in msg2, msg2


def test_honest_delta_counts_pass_the_recomputation():
    from coyodex.finalize import _stale_grounding_pin
    with tempfile.TemporaryDirectory() as tmp:
        live = ["kept", "added-since-the-pin"]
        p = make_grounding_map(tmp, live, claims_superseded=1, claims_added_since=1)
        v = make_verdicts_file(tmp, ["kept", "reconciled-away"])
        assert _stale_grounding_pin(p, live, [v]) is None


def test_no_value_of_claims_total_can_buy_silence():
    """Three escapes, one root. The first guard demanded the verdict set equal `claims_total`, so
    LOWERING the total went quiet; patching that direction left RAISING it, and a digit STRING,
    equally quiet — a more wrong record stayed safer than a less wrong one.

    The bounds consult `claims_total` not at all. For any partial verdict set P of the true pinned
    set T: `|P \\ L| <= |T \\ L|` and `|L \\ P| >= |L \\ T|`, so a superseded count BELOW what the
    verdicts already name, or an added count ABOVE what they leave room for, is provably wrong
    whatever subset was handed in."""
    from coyodex.finalize import _stale_grounding_pin
    with tempfile.TemporaryDirectory() as tmp:
        live = ["kept", "added-since"]
        v = make_verdicts_file(tmp, ["kept", "reconciled-away"])
        honest = make_grounding_map(tmp, live, claims_total=2,
                                    claims_superseded=1, claims_added_since=1)
        assert _stale_grounding_pin(honest, live, [v]) is None
        for label, total in (("lowered", 1), ("raised", 17), ("digit string", "2"), ("zero", 0)):
            cheat = Path(tmp) / f"cheat-{label}.json"
            cheat.write_text(json.dumps({"format": FORMAT, "title": "T", "goal": "g", "grounding": {
                "claims_total": total, "claims_challenged": 2, "claims_superseded": 0,
                "claims_added_since": 0,
                "live_claims_digest": __import__("coyodex.grounding", fromlist=["x"])
                .live_claims_digest(live)}}), encoding="utf-8")
            assert _stale_grounding_pin(cheat, live, [v]), f"{label} total bought silence"


def test_a_partial_verdict_set_still_stays_silent():
    """The honest case the guard exists for: `finalize` handed fewer files than the record was
    written against must not accuse it."""
    from coyodex.finalize import _stale_grounding_pin
    with tempfile.TemporaryDirectory() as tmp:
        live = ["kept", "added-since"]
        v = make_verdicts_file(tmp, ["kept"])          # 1 of the 2 pinned claims
        rec = make_grounding_map(tmp, live, claims_total=2,
                                 claims_superseded=1, claims_added_since=1)
        assert _stale_grounding_pin(rec, live, [v]) is None


def test_corrupting_claims_total_cannot_hide_a_wrong_digest():
    """The digest check used to sit BEHIND an early return for a missing or nonsensical
    `claims_total`, so a record bought silence by corrupting that field: 0, -5 and the string "446"
    all skipped the comparison even when the digest was provably another map's. Corrupting a field
    must never be safer than filling it in — the third appearance of that shape in this file."""
    from coyodex.finalize import _stale_grounding_pin
    from coyodex.grounding import live_claims_digest
    live = [f"claim {i}" for i in range(10)]
    other = [f"other {i}" for i in range(10)]          # same SIZE, different claims
    with tempfile.TemporaryDirectory() as tmp:
        for bad_total in (0, -5, "446", None):
            p = Path(tmp) / f"m{bad_total}.json"
            p.write_text(json.dumps({"format": FORMAT, "title": "T", "goal": "g", "grounding": {
                "claims_total": bad_total, "claims_challenged": 10,
                "live_claims_digest": live_claims_digest(other)}}), encoding="utf-8")
            msg = _stale_grounding_pin(p, live)
            assert msg and "live_claims_digest" in msg, (bad_total, msg)


def test_a_record_with_no_numbers_at_all_is_not_called_stale():
    """`validate` owns the malformed-record complaint. This command reports staleness, and a record
    with nothing in it is unfinished, not stale."""
    from coyodex.finalize import _stale_grounding_pin
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "m.json"
        p.write_text(json.dumps({"format": FORMAT, "title": "T", "goal": "g", "grounding": {}}),
                     encoding="utf-8")
        assert _stale_grounding_pin(p, ["a", "b"]) is None


def test_the_shape_line_names_the_access_surface():
    """The commit states the map's shape, and the access surface is part of it. Before the T7 fold
    the only mention of auth here was `len(m.security)`, gated on `if m.security:` — which the fold
    empties, so two real builds committed shapes that said nothing about 47 and 44 access rules."""
    root, p = make_repo()
    doc = json.loads(p.read_text())
    doc["rules"] = [
        {"id": "BR1", "statement": "Only an owner may cancel.", "access": True,
         "risk": "anyone could cancel", "sites": [{"where": "a.py:1", "why": "rejects"}]},
        {"id": "BR2", "statement": "A refund is capped at the paid amount.",
         "sites": [{"where": "b.py:2", "why": "clamps"}]}]
    p.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    report = finalize.build_report(p, root, [])
    block = finalize.gate_block(report, report.map_sha256)
    assert "2 business rules" in block, block
    assert "(1 access)" in block, block


def test_the_shape_line_says_nothing_about_access_when_there_is_none():
    """A map with no access rule must not gain an empty `(0 access)` clause."""
    root, p = make_repo()
    doc = json.loads(p.read_text())
    doc["rules"] = [{"id": "BR1", "statement": "A refund is capped.",
                     "sites": [{"where": "b.py:2", "why": "clamps"}]}]
    p.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    report = finalize.build_report(p, root, [])
    assert "access)" not in finalize.gate_block(report, report.map_sha256)


def test_the_disposition_table_keys_an_audit_advisory_on_the_pair_not_the_family():
    """`finalize` says every advisory is "either fixed or recorded under the extras heading its
    message names", and used to check nothing — nine shipped on one map neither fixed nor recorded,
    invisible because every read of the list had been narrowed by a grep.

    The first draft of the table reproduced the bug it reports on: reading every id under 'Audit
    exceptions' marked a `flow-title UC25` advisory "recorded" on the strength of an unrelated
    `actor-attribution UC25` line. A record adjudicates one (check, id) pair, never a family."""
    from coyodex.finalize import advisory_disposition, FinalizeReport, Leg, RAN
    import json, tempfile, os
    # UC25 must be DEFINED: candidate ids are intersected with the map's real id universe, because
    # shape alone cannot tell subsystem `S3` from Amazon S3, and a false id can flip a genuine gap
    # to "recorded". A map that references an id it never declares is not a realistic input.
    m = {"format": "coyodex-map", "title": "t", "goal": "g",
         "roles": [{"id": "R2", "name": "Admin", "kind": "human"}],
         "use_cases": [{"id": "UC25", "name": "Rebuild the graph", "actors": ["R2"],
                        "trigger_outcome": "an admin asks -> it rebuilds"}],
         "extras": [{"heading": "Audit exceptions",
                     "body": "actor-attribution UC25: the scheduler opens it, deliberate."}]}
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "m.json")
        with open(p, "w") as fh:
            json.dump(m, fh)
        rep = FinalizeReport(
            map_path=p, map_sha256="x", verdict="ADVISORIES",
            legs=[Leg("audit", RAN, advisory=[
                "flow-title: UC25 — a renamed use case whose flow was never re-traced. "
                "Record 'flow-title <id>: <why>' under an 'Audit exceptions' extras heading.",
                "actor-attribution: UC25 — declared actors do not include the opener. "
                "Record 'actor-attribution <id>: <why>' under an 'Audit exceptions' extras heading."])],
            advisory_total=2, blocking_total=0)
        by_msg = {a.split(":", 1)[0]: d for d, _h, a in advisory_disposition(Path(p), rep)}
    assert by_msg["flow-title"] == "UNRECORDED", "an unrelated check's record must not count"
    assert by_msg["actor-attribution"] == "recorded"


def test_the_table_never_says_recorded_without_naming_the_key_that_records_it():
    """The first draft defaulted to `recorded` whenever a heading existed and the advisory carried
    no id — so it reported "recorded" for an advisory whose own text reads "and no granularity
    record". That is the exact failure the table exists to catch, committed by the table.

    And a DISCLOSURE — an advisory that reports what a record silenced — is not an advisory asking
    to be recorded. Marking those `recorded` filed the whole "a recorded gap is still a gap" family
    under "handled", cancelling the disclosure that had just been added to raise it."""
    from coyodex.finalize import advisory_disposition, FinalizeReport, Leg, RAN
    import json, tempfile, os
    m = {"format": "coyodex-map", "title": "t", "goal": "g",
         "extras": [{"heading": "Balance exceptions", "body": "granularity: deliberate.\nUC2: fine."}]}
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "m.json")
        with open(p, "w") as fh:
            json.dump(m, fh)
        rep = FinalizeReport(
            map_path=p, map_sha256="x", verdict="ADVISORIES",
            legs=[Leg("validate", RAN, advisory=[
                "44 `access: true` rule(s) and no granularity record — record "
                "'security-granularity: <why>' under a 'Balance exceptions' extras heading",
                "66 component(s) with unclaimed surfaces are suppressed by a recorded "
                "'Unclaimed surfaces' line and counted as CLAIMED because of it: C1, C2"])],
            advisory_total=2, blocking_total=0)
        got = [d for d, _h, _a in advisory_disposition(Path(p), rep)]
    assert got[0] != "recorded", "an unrecorded advisory must never be filed as recorded"
    assert got[1] == "disclosure", "a disclosure of records is not itself a recordable advisory"
