"""`coyodex grounding write` — the record `validate` blocks on, derived instead of hand-tallied."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from coyodex import grounding as G  # noqa: E402
from coyodex.grounding import build_record, main  # noqa: E402


def make_worklist(*claims: str) -> list[str]:
    return list(claims)


def make_votes(*rows: tuple[str, object]) -> list[dict]:
    return [{"claim": c, "grounded": g, "evidence": "a/b.py:1"} for c, g in rows]


def test_the_four_counts_add_up_to_challenged():
    """The arithmetic `validate` BLOCKS on. Derived, so it cannot drift from the verdicts."""
    rec, errs = build_record(make_worklist("A", "B", "C"),
                             make_votes(("A", True), ("B", False), ("C", "unverifiable")))
    assert not errs
    assert rec["claims_confirmed"] + rec["claims_refuted"] + rec["claims_unverifiable"] \
        == rec["claims_challenged"] == 3
    assert (rec["claims_confirmed"], rec["claims_refuted"], rec["claims_unverifiable"]) == (1, 1, 1)


def test_a_tie_is_unverifiable_not_a_silent_win():
    """1-1 is not settled by the code. Crediting either side is the failure the record exists to
    prevent, so an unsettled claim lands in the honest third bucket."""
    rec, errs = build_record(make_worklist("A"), make_votes(("A", True), ("A", False)))
    assert not errs
    assert rec["claims_unverifiable"] == 1 and rec["claims_confirmed"] == 0


def test_it_refuses_a_worklist_snapshot_the_verdicts_do_not_match():
    """The snapshot problem, reproduced from a live build: re-deriving the worklist AFTER the
    refutations are applied leaves verdicts referring to claims the map no longer holds, and the
    resulting record makes `claims_challenged` exceed `claims_total` — which `validate` blocks on."""
    _rec, errs = build_record(make_worklist("A"), make_votes(("A", True), ("GONE", False)))
    assert any("not in the pinned worklist" in e for e in errs)


def test_it_refuses_when_a_claim_has_no_verdict():
    """"The gate did not run" must never read as "the gate passed" — an unchallenged claim would
    otherwise be silently excluded and the pass would read as complete."""
    _rec, errs = build_record(make_worklist("A", "B"), make_votes(("A", True)))
    assert any("have NO verdict" in e for e in errs)


# --- a DELIBERATE partial pass (`--partial`) ---------------------------------------

def make_partial_pass(partial: bool, note: str = "top of the ranked worklist, 1 of 3"):
    """Three ranked claims, one challenged — the shape of every real budget-limited pass."""
    return build_record(make_worklist("A", "B", "C"), make_votes(("A", True)),
                        note=note, partial=partial)


def test_a_partial_pass_keeps_the_FULL_surface_in_claims_total():
    """The number that matters. The old workaround — shrink the pinned worklist to what you
    challenged — put `1` here, so a 319-of-1608 pass shipped looking like a complete pass over a
    small map and the real surface survived only in prose no gate can read."""
    rec, errs = make_partial_pass(True)
    assert not errs, errs
    assert rec["claims_total"] == 3
    assert rec["claims_challenged"] == 1


def test_a_partial_record_still_satisfies_the_arithmetic_validate_blocks_on():
    # confirmed + refuted + unverifiable == challenged, NOT == total. The counts were always right
    # for a partial pass; only the refusal stood in the way.
    rec, _ = make_partial_pass(True)
    split = sum(int(rec[k]) for k in  # type: ignore[call-overload]
                ("claims_confirmed", "claims_refuted", "claims_unverifiable"))
    assert split == rec["claims_challenged"]


def test_partial_needs_a_note_saying_what_was_prioritized():
    """Counts say how many were challenged, never why those ones. Without that, a deliberate pass
    and an abandoned one are the same record."""
    _rec, errs = make_partial_pass(True, note="   ")
    assert any("needs a `--note`" in e for e in errs)


def test_partial_on_a_COMPLETE_pass_is_refused():
    """A finished verification that calls itself partial understates itself, and the next reader
    cannot tell which it was."""
    _rec, errs = build_record(make_worklist("A"), make_votes(("A", True)),
                              note="all of it", partial=True)
    assert any("every worklist claim has a verdict" in e for e in errs)


def test_partial_does_NOT_lift_the_wrong_snapshot_refusal():
    """The flag says "I challenged a subset on purpose" — it says nothing about verdicts for claims
    that were never in the worklist, which is the snapshot bug and still fatal."""
    _rec, errs = build_record(make_worklist("A", "B"), make_votes(("A", True), ("GONE", False)),
                             note="top slice", partial=True)
    assert any("not in the pinned worklist" in e for e in errs)


def test_without_the_flag_the_refusal_names_the_way_forward():
    # A refusal an operator cannot act on is where the hand-written record comes back.
    _rec, errs = make_partial_pass(False)
    assert any("--partial" in e and "--note" in e for e in errs)


def test_cli_writes_a_fragment_that_is_a_grounding_block():
    with tempfile.TemporaryDirectory() as td:
        _cli_writes_a_fragment(Path(td))


def _cli_writes_a_fragment(tmp_path: Path) -> None:
    wl = tmp_path / "audit.json"
    wl.write_text(json.dumps({"worklist": [{"claim": "A"}, {"claim": "B"}]}), encoding="utf-8")
    vd = tmp_path / "v.json"
    vd.write_text(json.dumps({"grounding": [
        {"claim": "A", "grounded": True, "evidence": "a.py:1"},
        {"claim": "B", "grounded": False}]}), encoding="utf-8")
    out = tmp_path / "grounding.json"
    assert main(["write", "--worklist", str(wl), "--verdicts", str(vd), "--out", str(out)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert set(payload) == {"grounding"}
    assert payload["grounding"]["claims_total"] == 2
    assert payload["grounding"]["claims_refuted"] == 1


def test_cli_exits_nonzero_when_it_refuses():
    """A refusal that exits 0 is the "printed an error and claimed success" failure."""
    with tempfile.TemporaryDirectory() as td:
        _cli_exits_nonzero(Path(td))


def _cli_exits_nonzero(tmp_path: Path) -> None:
    wl = tmp_path / "audit.json"
    wl.write_text(json.dumps({"worklist": [{"claim": "A"}, {"claim": "B"}]}), encoding="utf-8")
    vd = tmp_path / "v.json"
    vd.write_text(json.dumps({"grounding": [{"claim": "A", "grounded": True}]}), encoding="utf-8")
    assert main(["write", "--worklist", str(wl), "--verdicts", str(vd)]) == 1


def test_cli_partial_flag_writes_the_record_the_bare_run_refuses():
    """The same inputs, through the real CLI: refused without the flag, written with it — and the
    written record keeps the full surface in `claims_total`."""
    with tempfile.TemporaryDirectory() as td:
        _cli_partial_flag(Path(td))


def _cli_partial_flag(tmp_path: Path) -> None:
    wl = tmp_path / "audit.json"
    wl.write_text(json.dumps({"worklist": [{"claim": "A"}, {"claim": "B"}, {"claim": "C"}]}),
                  encoding="utf-8")
    vd = tmp_path / "v.json"
    vd.write_text(json.dumps({"grounding": [{"claim": "A", "grounded": True}]}), encoding="utf-8")
    out = tmp_path / "grounding.json"
    base = ["write", "--worklist", str(wl), "--verdicts", str(vd), "--out", str(out)]
    assert main(base) == 1                       # no flag -> refused, as before
    assert not out.exists()                      # a refusal writes nothing
    assert main([*base, "--partial", "--note", "ranked top-down; 1 of 3 in budget"]) == 0
    rec = json.loads(out.read_text(encoding="utf-8"))["grounding"]
    assert (rec["claims_total"], rec["claims_challenged"]) == (3, 1)
    assert "1 of 3" in rec["note"]


# --- grounding report, skeptic ids, and the stale pin ------------------------------------------


def test_report_lists_which_claims_were_refuted_not_only_how_many():
    """`write` resolves every claim and emits four counts, so a build that must reconcile each
    refutation had nothing to read — one hand-wrote a 12-line vote aggregator one turn later."""
    claims = ["C1 calls C2", "C3 reads E1", "C4 persists E2"]
    rows = [{"claim": "C1 calls C2", "grounded": True, "evidence": "a.py:1"},
            {"claim": "C3 reads E1", "grounded": False, "evidence": "b.py:2",
             "note": "b.py:2 writes, it never reads"},
            {"claim": "C4 persists E2", "grounded": "unverifiable", "evidence": ""}]
    out = G.format_report(claims, rows)
    assert "REFUTED" in out and "C3 reads E1" in out
    assert "UNVERIFIABLE" in out and "C4 persists E2" in out
    assert "C1 calls C2" not in out.split("confirmed:")[0], "a confirmed claim is not a worklist item"
    assert "confirmed: 1 of 3" in out


def test_report_separates_a_tie_from_a_stated_unverifiable():
    """`_verdict_bucket` files both under `unverifiable` — right for the count, wrong for the
    reader. A live build's grounding note described four unverifiables as one kind when two were
    the other."""
    claims = ["C1 calls C2"]
    rows = [{"claim": "C1 calls C2", "grounded": True, "evidence": "a.py:1", "skeptic": "sec-a"},
            {"claim": "C1 calls C2", "grounded": False, "evidence": "a.py:9", "skeptic": "sec-b"}]
    out = G.format_report(claims, rows)
    assert "TIED" in out
    assert "1 for / 1 against" in out
    assert "sec-a" in out and "sec-b" in out


def test_report_names_the_claims_that_were_never_challenged():
    out = G.format_report(["C1 calls C2", "C3 reads E1"],
                          [{"claim": "C1 calls C2", "grounded": True, "evidence": "a.py:1"}])
    assert "NO VERDICT" in out and "C3 reads E1" in out


def test_two_skeptics_agreeing_are_not_reported_as_a_duplicate_row():
    """The method PRESCRIBES a double read of the security claims, and the note used to tell the
    build to "drop one" for doing exactly what it was asked to do."""
    from coyodex.anchor_drift import load_verdicts
    with tempfile.TemporaryDirectory() as tmp:
        rows = [{"claim": "C1 calls C2", "grounded": True, "evidence": "a.py:1"}]
        a, b = Path(tmp) / "v-a.json", Path(tmp) / "v-b.json"
        a.write_text(json.dumps({"grounding": [{**rows[0], "skeptic": "sec-a"}]}), encoding="utf-8")
        b.write_text(json.dumps({"grounding": [{**rows[0], "skeptic": "sec-b"}]}), encoding="utf-8")
        _loaded, notes = load_verdicts([str(a), str(b)])
        assert notes == [], notes


def test_the_same_skeptic_id_in_two_files_is_still_reported():
    from coyodex.anchor_drift import load_verdicts
    with tempfile.TemporaryDirectory() as tmp:
        row = {"claim": "C1 calls C2", "grounded": True, "evidence": "a.py:1", "skeptic": "sec-a"}
        a, b = Path(tmp) / "v-a.json", Path(tmp) / "agg.json"
        a.write_text(json.dumps({"grounding": [row]}), encoding="utf-8")
        b.write_text(json.dumps({"grounding": [row]}), encoding="utf-8")
        _loaded, notes = load_verdicts([str(a), str(b)])
        assert len(notes) == 1 and "SAME `skeptic` id" in notes[0]


def test_the_record_states_the_delta_when_given_the_live_map():
    """Without `--map` the record cannot say how the shipped map differs from the pinned worklist,
    and a build had no legal answer to the staleness advisory."""
    from coyodex.grounding import build_record, live_claims_digest
    pinned = ["a", "b", "c"]
    rows = [{"claim": c, "grounded": True, "evidence": "f.py:1"} for c in pinned]
    live = ["a", "b", "d"]                       # c was reconciled away; d was authored since
    rec, errors = build_record(pinned, rows, live_claims=live)
    assert not errors
    assert rec["claims_total"] == 3 and rec["claims_challenged"] == 3
    assert rec["claims_superseded"] == 1 and rec["claims_added_since"] == 1
    assert rec["live_claims_digest"] == live_claims_digest(live)


def test_without_the_live_map_the_record_is_exactly_as_before():
    """`--map` is optional: a build that never reconciles a count-changing refutation needs none of
    this, and its record must not grow fields it cannot fill honestly."""
    from coyodex.grounding import build_record
    pinned = ["a", "b"]
    rows = [{"claim": c, "grounded": True, "evidence": "f.py:1"} for c in pinned]
    rec, errors = build_record(pinned, rows)
    assert not errors
    for field in ("claims_superseded", "claims_added_since", "live_claims_digest"):
        assert field not in rec, field


def test_the_digest_ignores_order_and_duplication():
    """Both sides are counted over the de-duplicated claim SET — two sides counted by different
    rules measure the rule instead of the map."""
    from coyodex.grounding import live_claims_digest
    assert live_claims_digest(["b", "a"]) == live_claims_digest(["a", "b"])
    assert live_claims_digest(["a", "a", "b"]) == live_claims_digest(["a", "b"])
    assert live_claims_digest(["a", "b"]) != live_claims_digest(["a", "c"])


def test_the_pinned_split_is_never_recomputed_against_the_live_map():
    """The `refuted 0` trap, pinned as a test. The claims a reconcile deletes are exactly the
    REFUTED ones, so a split measured against the live worklist reports that nothing was ever found
    wrong. The split must stay pinned no matter what `--map` says."""
    from coyodex.grounding import build_record
    pinned = ["kept", "refuted-and-rewritten"]
    rows = [{"claim": "kept", "grounded": True, "evidence": "f.py:1"},
            {"claim": "refuted-and-rewritten", "grounded": False, "note": "wrong"}]
    rec, _ = build_record(pinned, rows, live_claims=["kept", "the rewritten form"])
    assert rec["claims_refuted"] == 1, "the refutation must survive the live comparison"
    assert rec["claims_superseded"] == 1


def test_the_digest_is_not_ambiguous_about_where_a_claim_ends():
    """A separator that can appear inside a claim makes the digest ambiguous: newline-joined,
    `["a\\nb"]` hashed identically to `["a", "b"]`. No claim carries a newline today, which is why
    it was worth removing before one does."""
    from coyodex.grounding import live_claims_digest
    assert live_claims_digest(["a\nb"]) != live_claims_digest(["a", "b"])


def test_report_lists_which_claims_were_superseded():
    """The record says how MANY claims the reconcile removed; nothing could say WHICH, and the whole
    design rests on those being the refuted ones. `--map` used to be accepted and discarded here."""
    import contextlib
    import io
    import json as _json
    import tempfile
    from pathlib import Path
    from coyodex import grounding
    with tempfile.TemporaryDirectory() as tmp:
        wl = Path(tmp) / "wl.json"
        wl.write_text(_json.dumps({"worklist": [{"claim": c} for c in
                                                ("kept", "reconciled-away", "confirmed-then-cut")]}))
        v = Path(tmp) / "v.json"
        v.write_text(_json.dumps({"grounding": [
            {"claim": "kept", "grounded": True, "evidence": "f.py:1"},
            {"claim": "reconciled-away", "grounded": False, "note": "wrong"},
            {"claim": "confirmed-then-cut", "grounded": True, "evidence": "g.py:2"}]}))
        m = Path(tmp) / "m.json"
        m.write_text(_json.dumps({"format": "coyodex-map", "title": "T", "goal": "g",
                                  "components": [{"id": "C1", "name": "A", "source": "f.py:1"}]}))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = grounding.main(["report", "--worklist", str(wl), "--verdicts", str(v),
                                   "--map", str(m)])
        out = buf.getvalue()
    assert code == 0, out
    assert "SUPERSEDED (3)" in out, out
    # the one that was CONFIRMED and cut anyway is the interesting case, and is called out
    assert "confirmed-then-cut" in out and "was CONFIRMED" in out, out
    assert "CONFIRMED — the build rewrote a claim the skeptics had settled" in out, out


def make_report(pinned: list[str], rows: list[dict], live: list[str] | None) -> str:
    from coyodex.grounding import format_report
    return format_report(pinned, rows, live_claims=live)


def test_an_unvoted_claim_can_be_superseded_too():
    """The unvoted branch returned before the superseded check, so the report listed FEWER
    superseded claims than `write --map` counted — silently, in the tool the record points a reader
    at to see which."""
    pinned = ["kept", "never-challenged-and-cut"]
    rows = [{"claim": "kept", "grounded": True, "evidence": "f.py:1"}]
    text = make_report(pinned, rows, live=["kept"])
    assert "SUPERSEDED (1)" in text and "never-challenged-and-cut" in text


def test_only_a_confirmed_verdict_counts_as_settled():
    """A tie is by definition unsettled — the report's own next section says "the skeptics split;
    adjudicate against the code" — and an unverifiable verdict says the code could not answer.
    Calling all three "settled" over-claimed on two of them."""
    pinned = ["tied-and-cut", "unverifiable-and-cut", "confirmed-and-cut"]
    rows = [{"claim": "tied-and-cut", "grounded": True, "evidence": "a.py:1"},
            {"claim": "tied-and-cut", "grounded": False},
            {"claim": "unverifiable-and-cut", "grounded": "unverifiable"},
            {"claim": "confirmed-and-cut", "grounded": True, "evidence": "b.py:2"}]
    text = make_report(pinned, rows, live=[])
    assert "1 of these was CONFIRMED" in text, text
    assert "2 were never settled" in text, text


def test_the_superseded_list_shows_the_vote_split():
    """2-1 and 3-0 read identically without it — and a live report described a 2-1 override as
    "three skeptics agreed"."""
    pinned = ["c"]
    rows = [{"claim": "c", "grounded": True, "evidence": "a.py:1"},
            {"claim": "c", "grounded": True, "evidence": "a.py:1"},
            {"claim": "c", "grounded": False}]
    assert "[2 for / 1 against]" in make_report(pinned, rows, live=[])


def test_report_names_a_refutation_the_superseded_count_cannot_witness():
    """`claims_superseded` counts pinned claims the shipped map no longer carries, and the design
    reads that as "the refutations landed". A refutation can be reconciled WITHOUT changing the
    claim's rendered text: on a live build `E35 (UpstreamState) has states […] with 10
    transition(s)` was refuted, the wrong transition was corrected, and the claim string came out
    identical — 5 refutations, 4 superseded. The digest cannot witness that fifth fix at all, so a
    build that "corrected" it by doing nothing would produce the same digest."""
    claims = ["C1 calls C2", "E35 has states [a, b] with 10 transition(s)"]
    rows = [{"claim": "C1 calls C2", "grounded": False, "evidence": "a.py:1"},
            {"claim": "E35 has states [a, b] with 10 transition(s)", "grounded": False,
             "evidence": "s.py:41", "note": "the live -> deferred transition has no code path"}]
    # C1 calls C2 was DROPPED by the reconcile; the E35 claim still renders identically.
    live = ["E35 has states [a, b] with 10 transition(s)"]
    out = G.format_report(claims, rows, live_claims=live)
    assert "SUPERSEDED (1)" in out, out
    assert "REFUTED BUT NOT SUPERSEDED (1)" in out, out
    assert "E35 has states" in out.split("REFUTED BUT NOT SUPERSEDED")[1]


def test_report_says_nothing_extra_when_every_refutation_was_superseded():
    """The normal case must stay quiet, or the line becomes noise a build learns to skip."""
    claims = ["C1 calls C2"]
    rows = [{"claim": "C1 calls C2", "grounded": False, "evidence": "a.py:1"}]
    out = G.format_report(claims, rows, live_claims=[])
    assert "SUPERSEDED (1)" in out
    assert "NOT SUPERSEDED" not in out


# --- the note, without the shell -------------------------------------------------
# `--note` is required, so a re-run (the ordinary case: the record is re-measured after a late fix)
# had to re-supply the whole note. A live build did it through a nested `$(python -c …)` that
# pushed ~1900 characters back through the shell — it survived, but a note containing a quote or a
# backtick would not have.


def make_write_inputs(td: str) -> tuple[str, str]:
    wl = Path(td) / "worklist.json"
    wl.write_text(json.dumps({"worklist": [{"claim": "C1 calls C2"}]}), encoding="utf-8")
    vd = Path(td) / "verdicts.json"
    vd.write_text(json.dumps({"grounding": [
        {"claim": "C1 calls C2", "grounded": True, "evidence": "a.py:1"}]}), encoding="utf-8")
    return str(wl), str(vd)


def test_note_file_carries_a_note_the_shell_would_have_mangled():
    tricky = 'has a "quote", a `backtick` and a $(subshell)'
    with tempfile.TemporaryDirectory() as td:
        wl, vd = make_write_inputs(td)
        nf = Path(td) / "note.txt"
        nf.write_text(tricky, encoding="utf-8")
        out = Path(td) / "grounding.json"
        assert main(["write", "--worklist", wl, "--verdicts", vd, "--out", str(out),
                     "--note-file", str(nf)]) == 0
        assert json.loads(out.read_text())["grounding"]["note"] == tricky


def test_keep_note_reuses_the_note_already_written():
    with tempfile.TemporaryDirectory() as td:
        wl, vd = make_write_inputs(td)
        out = Path(td) / "grounding.json"
        assert main(["write", "--worklist", wl, "--verdicts", vd, "--out", str(out),
                     "--note", "the original reasoning"]) == 0
        # the re-run, with no note re-supplied
        assert main(["write", "--worklist", wl, "--verdicts", vd, "--out", str(out),
                     "--keep-note"]) == 0
        assert json.loads(out.read_text())["grounding"]["note"] == "the original reasoning"


def test_keep_note_refuses_when_there_is_no_prior_note(capsys):
    with tempfile.TemporaryDirectory() as td:
        wl, vd = make_write_inputs(td)
        out = Path(td) / "grounding.json"
        assert main(["write", "--worklist", wl, "--verdicts", vd, "--out", str(out),
                     "--keep-note"]) == 2
        assert "found no note" in capsys.readouterr().err


def test_keep_note_and_note_file_together_are_refused(capsys):
    with tempfile.TemporaryDirectory() as td:
        wl, vd = make_write_inputs(td)
        nf = Path(td) / "note.txt"
        nf.write_text("x", encoding="utf-8")
        assert main(["write", "--worklist", wl, "--verdicts", vd, "--out",
                     str(Path(td) / "g.json"), "--keep-note", "--note-file", str(nf)]) == 2
        assert "Pick one" in capsys.readouterr().err


def test_a_worklist_given_as_a_bare_list_is_read_not_crashed_on():
    """`coyodex audit --json | jq .worklist` yields a BARE LIST, which is the obvious way to hand
    this command its input — and it crashed with an AttributeError traceback.

    The list case was already intended: the `isinstance` test existed. It sat inside the default
    argument of `.get()`, so reaching it required the very attribute access that had already
    raised. A guard in an unreachable position is not a guard, and the one input shape it was
    written for was the one that failed."""
    import json, tempfile, os
    from coyodex.grounding import _worklist_claims
    from pathlib import Path
    rows = [{"claim": "C1 calls C2", "anchor": "a.py:1"}, {"claim": "C2 writes E1"}]
    with tempfile.TemporaryDirectory() as d:
        bare = Path(d) / "bare.json"
        bare.write_text(json.dumps(rows))
        wrapped = Path(d) / "wrapped.json"
        wrapped.write_text(json.dumps({"worklist": rows}))
        assert _worklist_claims(bare) == ["C1 calls C2", "C2 writes E1"]
        assert _worklist_claims(wrapped) == _worklist_claims(bare), \
            "both shapes must read identically — the wrapper is presentation, not meaning"


def _write(tmp, name, obj):
    import json
    from pathlib import Path
    p = Path(tmp) / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj))
    return str(p)


def test_lint_catches_the_quoted_boolean_at_the_skeptic_not_a_hundred_turns_later():
    """`grounding write` already refuses this — at the END of the build, where the skeptic that
    produced it finished long ago. One live build shipped 40 rows with `grounded` as the STRING
    "true" and paid four turns of hand-repair on the critical path. The skeptic's own self-check
    could not have caught it: printing str(value) renders 'true' for a string and a boolean alike."""
    import tempfile
    from coyodex.grounding import lint_verdicts
    with tempfile.TemporaryDirectory() as d:
        bad = _write(d, "v.json", {"grounding": [
            {"claim": "c", "grounded": "true", "evidence": "a.py:1", "skeptic": "s", "note": "n"}]})
        assert any("unrecognised" in p for p in lint_verdicts([bad]).problems)
        good = _write(d, "g.json", {"grounding": [
            {"claim": "c", "grounded": True, "evidence": "a.py:1", "skeptic": "s", "note": "n"},
            {"claim": "d", "grounded": "unverifiable", "evidence": "b.py:2", "skeptic": "s",
             "note": "n"}]})
        assert not lint_verdicts([good]).problems, "both legal shapes must pass"


def test_lint_catches_a_note_claiming_a_read_the_agent_never_made():
    """The worst thing a retrospective found: a skeptic settled 40 claims in 95 seconds from one
    directory-wide grep, generated every row from a script, and opened each note `Read <file>:` for
    files it never opened. Forty fabricated confirmations reached a shipped grounding record and
    nothing in the toolchain could see them. The agent's own transcript can."""
    import tempfile, json
    from pathlib import Path
    from coyodex.grounding import lint_verdicts
    with tempfile.TemporaryDirectory() as d:
        agents = Path(d) / "agents"
        agents.mkdir()
        (agents / "agent-a1.jsonl").write_text(json.dumps(
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Bash",
                 "input": {"command": "sed -n 1,60p db/schema/workspaces.ts"}}]}}) + "\n")
        v = _write(d, "v.json", {"grounding": [
            {"claim": "c1", "grounded": True, "evidence": "x:1", "skeptic": "a1",
             "note": "Read db/schema/workspaces.ts: it does"},
            {"claim": "c2", "grounded": True, "evidence": "y:1", "skeptic": "a1",
             "note": "Read db/schema/never_opened.ts: it does"}]})
        problems = lint_verdicts([v], agents).problems
        assert any("never_opened.ts" in p for p in problems), problems
        assert not any("workspaces.ts" in p for p in problems), \
            "the file it really did open must not be accused"
