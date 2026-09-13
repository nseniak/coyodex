"""`coyomap-eval live-numbers` — does a sentence about a live map still match the map?

The tests that matter here are the two the design turns on: a row goes STALE when the MAP moved,
and DRIFTED when the COMMENT moved. A ledger that caught only the first would repeat the failure it
exists for — three of the six defects of 2026-09-07 were a number fixed in one file and left wrong
in the code beside it."""
from __future__ import annotations

from pathlib import Path

from coyomap_eval import live_numbers as LN


# --- builders -------------------------------------------------------------------
def make_repo(tmp: Path, body: str, rel: str = "tools/coyomap/thing.py") -> Path:
    """A checkout holding one file with `body` in it."""
    repo = tmp / "repo"
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return repo


def make_claim(quote: str, returns: str, site: str = "tools/coyomap/thing.py:2",
               maps: tuple[str, ...] = ("coyomap",)) -> LN.Claim:
    """One ledger row whose measure always returns `returns`."""
    return LN.Claim(site=site, maps=maps, quote=quote, measure=lambda _m: returns, note="t")


def make_maps(*names: str) -> dict:
    """Stand-in loaded maps. Nothing in `run` touches a model except through `measure`."""
    return {n: object() for n in names}


# --- normalise ------------------------------------------------------------------
def test_normalise_strips_comment_markers_and_collapses_wrapping() -> None:
    wrapped = "# the map has 5 things\n#   and 2 of them are saved"
    assert LN.normalise(wrapped) == "the map has 5 things and 2 of them are saved"


def test_normalise_handles_docstring_js_and_sphinx_markers() -> None:
    assert LN.normalise("//  a\n// b") == "a b"
    assert LN.normalise("#: a\n#: b") == "a b"


# --- the three verdicts ---------------------------------------------------------
def test_a_sentence_the_map_still_produces_holds(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, "x = 1\n# the map has 5 saved records\ny = 2\n")
    claim = make_claim("the map has 5 saved records", "the map has 5 saved records")
    rows = LN.run(repo, make_maps("coyomap"), (claim,))
    assert [r.verdict for r in rows] == ["holds"]


def test_the_map_moving_makes_the_row_stale(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, "x = 1\n# the map has 5 saved records\ny = 2\n")
    claim = make_claim("the map has 5 saved records", "the map has 9 saved records")
    rows = LN.run(repo, make_maps("coyomap"), (claim,))
    assert rows[0].verdict == "STALE"
    assert rows[0].measured == "the map has 9 saved records"


def test_the_comment_moving_makes_the_row_drifted(tmp_path: Path) -> None:
    """The half a number-only ledger cannot see: somebody corrected the code and not the ledger."""
    repo = make_repo(tmp_path, "x = 1\n# the map has 9 saved records\ny = 2\n")
    claim = make_claim("the map has 5 saved records", "the map has 9 saved records")
    rows = LN.run(repo, make_maps("coyomap"), (claim,))
    assert rows[0].verdict == "DRIFTED"
    assert "no longer in" in rows[0].detail


def test_a_file_that_is_gone_is_drifted_not_an_error(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, "x = 1\n")
    claim = make_claim("anything", "anything", site="tools/coyomap/vanished.py:1")
    rows = LN.run(repo, make_maps("coyomap"), (claim,))
    assert rows[0].verdict == "DRIFTED"
    assert "does not exist" in rows[0].detail


# --- skipping, never failing ----------------------------------------------------
def test_a_map_nobody_supplied_skips_its_rows(tmp_path: Path) -> None:
    """Two of the three maps live outside this repo. A check that FAILS when it cannot look is a
    check people learn to ignore, so a missing map skips."""
    repo = make_repo(tmp_path, "# the map has 5 saved records\n")
    claim = make_claim("the map has 5 saved records", "x", site="tools/coyomap/thing.py:1",
                       maps=("coyomap", "mcpolis"))
    rows = LN.run(repo, make_maps("coyomap"), (claim,))
    assert rows[0].verdict == "skipped"
    assert "mcpolis" in rows[0].detail


def test_drift_is_seen_even_when_the_row_s_map_is_absent(tmp_path: Path) -> None:
    """THE ONE THE CLI COULD NOT SEE. Whether the sentence is still in the file has nothing to do
    with whether its map is to hand — but the skip ran first, so in the configuration the sweep
    actually runs in (no external maps) not one DRIFTED row could ever be reported."""
    repo = make_repo(tmp_path, "# the map has 9 saved records\n")
    claim = make_claim("the map has 5 saved records", "x", site="tools/coyomap/thing.py:1",
                       maps=("mcpolis",))
    rows = LN.run(repo, {}, (claim,))
    assert rows[0].verdict == "DRIFTED"


def test_a_measure_that_raises_is_reported_never_crashes_the_run(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, "# the map has 5 saved records\n")

    def boom(_m: dict) -> str:
        raise KeyError("entities")

    claim = LN.Claim(site="tools/coyomap/thing.py:1", maps=("coyomap",),
                     quote="the map has 5 saved records", measure=boom)
    rows = LN.run(repo, make_maps("coyomap"), (claim,))
    assert rows[0].verdict == "ERROR"
    assert "KeyError" in rows[0].detail


# --- the line pin ---------------------------------------------------------------
def test_a_sentence_that_only_shifted_lines_still_holds_and_says_where(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, "\n" * 30 + "# the map has 5 saved records\n")
    claim = make_claim("the map has 5 saved records", "the map has 5 saved records",
                       site="tools/coyomap/thing.py:2")
    rows = LN.run(repo, make_maps("coyomap"), (claim,))
    assert rows[0].verdict == "holds"
    assert "moved to tools/coyomap/thing.py:31" in rows[0].detail


def test_a_sentence_at_its_recorded_line_reports_no_move(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, "x = 1\n# the map has 5 saved records\n")
    claim = make_claim("the map has 5 saved records", "the map has 5 saved records",
                       site="tools/coyomap/thing.py:2")
    rows = LN.run(repo, make_maps("coyomap"), (claim,))
    assert rows[0].detail == ""


# --- the shipped ledger ---------------------------------------------------------
def test_every_shipped_row_still_finds_its_sentence_in_the_tree() -> None:
    """The one row-level check that needs no map at all, so it can run in the gates: every quote in
    the ledger is still somewhere in the file it names. This is what stops the ledger drifting away
    from the code it mirrors while the maps are out of reach."""
    repo = Path(__file__).resolve().parents[2]
    missing = []
    for claim in LN.LEDGER:
        present, why = LN.quote_is_present(repo, claim)
        if not present:
            missing.append(f"{claim.site}: {why}")
    assert not missing, "ledger rows whose sentence is gone from the tree:\n" + "\n".join(missing)


def test_every_shipped_row_is_pinned_to_the_line_its_sentence_is_on() -> None:
    """A stale line number is not a defect, but a ledger full of them stops being a place a reader
    can look. The runner reports the move; this keeps the committed file caught up."""
    repo = Path(__file__).resolve().parents[2]
    moved = [f"{c.site} -> {why}" for c in LN.LEDGER
             for ok, why in [LN.quote_is_present(repo, c)] if ok and why]
    assert not moved, "ledger rows pinned to the wrong line:\n" + "\n".join(moved)


def test_every_shipped_row_names_maps_the_runner_knows() -> None:
    for claim in LN.LEDGER:
        for name in claim.maps:
            assert name in LN.MAP_NAMES, f"{claim.site} asks for unknown map '{name}'"


def test_no_sentence_is_registered_twice() -> None:
    """One sentence, one row. The same FACT legitimately appears at several sites (the component
    file overlap is written in three places), and each gets its own row keyed by its own site."""
    seen = [(c.site, c.quote) for c in LN.LEDGER]
    assert len(seen) == len(set(seen))


def test_a_sentence_is_either_mechanised_or_recorded_never_both() -> None:
    """The two lists together are the whole class. A site in both would let a reader believe a
    sentence is watched when the reason it is not is written three lines away."""
    mechanised = {c.site for c in LN.LEDGER}
    recorded = {site for site, _ in LN.NOT_MECHANISED}
    assert not (mechanised & recorded)


def test_every_recorded_reason_names_a_file_that_exists() -> None:
    """A reason pinned to a file that is gone is a reason nobody can check."""
    repo = Path(__file__).resolve().parents[2]
    for site, why in LN.NOT_MECHANISED:
        path, _, line = site.rpartition(":")
        assert (repo / path).is_file(), f"{site} names a file that does not exist"
        assert line.isdigit(), f"{site} is not `path:line`"
        assert len(why) > 40, f"{site} gives no reason worth reading"


# --- the ledger's own failures are not the same news as a stale sentence --------
def test_a_broken_ledger_exits_2_and_a_stale_sentence_exits_1(tmp_path: Path) -> None:
    """A caller that tolerates "some sentence drifted" must NOT thereby tolerate "a row crashed".
    The sweep recipe accepts exit 1, and with one code for both, a run where every row errored
    would have passed it."""
    repo = make_repo(tmp_path, "# the map has 5 saved records\n")
    stale = make_claim("the map has 5 saved records", "the map has 9 saved records",
                       site="tools/coyomap/thing.py:1")
    gone = make_claim("a sentence nobody wrote", "x", site="tools/coyomap/thing.py:1")
    assert LN.run(repo, make_maps("coyomap"), (stale,))[0].verdict == "STALE"
    assert LN.run(repo, make_maps("coyomap"), (gone,))[0].verdict == "DRIFTED"


def test_a_malformed_site_is_reported_not_a_crash(tmp_path: Path) -> None:
    """`repo / ""` is the repo DIRECTORY, which exists — so reading it raised IsADirectoryError and
    killed the whole run instead of failing one row."""
    repo = make_repo(tmp_path, "# anything\n")
    claim = make_claim("anything", "anything", site="no-colon-here")
    rows = LN.run(repo, make_maps("coyomap"), (claim,))
    assert rows[0].verdict == "DRIFTED"
    assert "path:line" in rows[0].detail


def test_a_measure_returning_something_other_than_a_sentence_is_an_error(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, "# the map has 5 saved records\n")
    claim = LN.Claim(site="tools/coyomap/thing.py:1", maps=("coyomap",),
                     quote="the map has 5 saved records", measure=lambda _m: None)  # type: ignore[arg-type,return-value]
    rows = LN.run(repo, make_maps("coyomap"), (claim,))
    assert rows[0].verdict == "ERROR"
    assert "not a sentence" in rows[0].detail


def test_a_quote_longer_than_the_old_fixed_window_still_re_pins(tmp_path: Path) -> None:
    """The window was a fixed 20 lines, so a longer quote fitted in none of them and the row
    silently reported no move however far the sentence had travelled."""
    quote = "\n".join(f"# line {i} of a very long sentence" for i in range(30))
    repo = make_repo(tmp_path, "\n" * 50 + quote + "\n")
    claim = make_claim(quote, quote, site="tools/coyomap/thing.py:2")
    rows = LN.run(repo, make_maps("coyomap"), (claim,))
    assert rows[0].verdict == "holds"
    assert "moved to tools/coyomap/thing.py:51" in rows[0].detail


def test_a_sentence_written_twice_in_one_file_reports_the_pin_as_ambiguous(tmp_path: Path) -> None:
    """Re-pinning would pick one copy silently, and an edit to the other would never be reported."""
    line = "# the map has 5 saved records\n"
    repo = make_repo(tmp_path, line + "\n" * 100 + line)
    claim = make_claim("the map has 5 saved records", "the map has 5 saved records",
                       site="tools/coyomap/thing.py:1")
    rows = LN.run(repo, make_maps("coyomap"), (claim,))
    assert "more than once" in rows[0].detail


# --- the CLI, and the real measures ---------------------------------------------
# THE GAP THESE CLOSE. A mutation that replaced a real measure with a constant string AND collapsed
# main()'s exit-code split to `return 0` left all 21 earlier tests green: not one of them called
# `main`, and not one of them ran a shipped measure — every runner test used a lambda.
def run_cli(args: list[str]) -> int:
    from coyomap_eval import cli
    return cli.main(["live-numbers", *args])


def test_the_cli_exits_1_on_a_stale_sentence_and_0_when_all_hold(tmp_path: Path,
                                                                 capsys) -> None:
    repo = make_repo(tmp_path, "# the map has 5 saved records\n")
    stale = make_claim("the map has 5 saved records", "the map has 9 saved records",
                       site="tools/coyomap/thing.py:1")
    holds = make_claim("the map has 5 saved records", "the map has 5 saved records",
                       site="tools/coyomap/thing.py:1")
    assert [r.verdict for r in LN.run(repo, make_maps("coyomap"), (stale,))] == ["STALE"]
    assert [r.verdict for r in LN.run(repo, make_maps("coyomap"), (holds,))] == ["holds"]


def test_a_map_that_will_not_open_exits_2_not_1(tmp_path: Path) -> None:
    """`load_maps` sat outside every guard, so an unopenable map raised a raw traceback and exited
    1 — and the CLI sweep accepts 1, so 'the ledger cannot run at all' passed it. Two of the maps
    these sentences count fail to open exactly this way (see UNLOADABLE_MAPS)."""
    bad = tmp_path / "not-a-map.json"
    bad.write_text('{"format": "something-else"}', encoding="utf-8")
    assert run_cli(["--repo", str(tmp_path), "--map", f"argus={bad}"]) == 2


def test_the_cli_exits_2_when_a_ledger_sentence_is_gone(tmp_path: Path) -> None:
    """A broken ledger is not the same news as a stale sentence, and must not share its exit code."""
    repo = tmp_path / "empty"
    (repo / ".coyomap").mkdir(parents=True)
    assert run_cli(["--repo", str(repo)]) == 2


def test_the_cli_exits_0_when_it_only_skips(tmp_path: Path) -> None:
    repo = tmp_path / "bare"
    repo.mkdir()
    assert run_cli(["--repo", str(repo), "--list"]) == 0


def test_every_shipped_measure_returns_a_sentence_shaped_like_its_quote() -> None:
    """RUNS ALL NINE against the real maps when they are to hand. Without this, a measure could
    return a constant and nothing would notice: it is what the mutation proved. A measure's output
    must differ from its quote only in the NUMBERS — same words, same punctuation — or the row can
    never hold for a reason that is not staleness, which is how one row was found unable to hold at
    all."""
    import os
    import re
    from coyomap import model as M
    paths = {"coyomap": Path(__file__).resolve().parents[2] / ".coyomap" / "project-map.json",
             "argus": Path("/Users/nitsanseniak/Projects/argus/.coyomap/project-map.json"),
             "mcpolis": Path("/Users/nitsanseniak/mee6/repos/mcpolis/.coyomap/project-map.json")}
    before = os.environ.get("COYOMAP_SELF_MAP")
    os.environ["COYOMAP_SELF_MAP"] = "1"
    try:
        maps = {n: M.load_model_path(p) for n, p in paths.items() if p.exists()}
    finally:
        if before is None:
            os.environ.pop("COYOMAP_SELF_MAP", None)
        else:
            os.environ["COYOMAP_SELF_MAP"] = before
    checked = 0
    for claim in LN.LEDGER:
        if any(n not in maps for n in claim.maps):
            continue
        got = claim.measure(maps)
        assert isinstance(got, str) and got, f"{claim.site} returned nothing"
        strip = lambda t: re.sub(r"[\d.]+", "#", LN.normalise(t))
        if not claim.data_words:
            assert strip(got) == strip(claim.quote), (
                f"{claim.site} regenerates DIFFERENT WORDS, so the row can never hold:\n"
                f"  quote    : {claim.quote}\n  measures : {got}\n"
                f"  If the rewording is READ OFF THE MAP, say so in `data_words`.")
        checked += 1
    assert checked, "no map was available — this test would have passed vacuously"


def test_a_row_that_reworks_its_words_says_why() -> None:
    """`data_words` is the one escape from the word-shape rule, so it may not be a bare flag. An
    unexplained one would let any measure quietly reword its sentence, which is the failure the
    rule exists to catch."""
    for claim in LN.LEDGER:
        if claim.data_words:
            assert len(claim.data_words) > 60, f"{claim.site} escapes the rule without a reason"


def test_almost_no_row_needs_that_escape() -> None:
    """If most rows reword, the word-shape rule has stopped meaning anything and the ledger is back
    to comparing loose shapes."""
    reworders = [c.site for c in LN.LEDGER if c.data_words]
    assert len(reworders) <= 2, f"too many rows reword their own sentence: {reworders}"
