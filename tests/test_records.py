#!/usr/bin/env python3
"""Tests for `coyodex.records` — the ONE reader for recorded-exception lines.

Four families used to parse that one line shape with four regexes, and three of them carry a comment
describing a real incident where the regex mis-read a key and OVER-suppressed. These tests pin the
shared contract: what a record is, what a multi-key record is, what records nothing (and says so),
and which headings are the map's own build record rather than notes about the code.

Run either way (needs an editable install: `make deps`):
    python3 tests/test_records.py
    pytest tests/test_records.py
"""
from __future__ import annotations

import re
from pathlib import Path

from coyodex import records
from coyodex.model import ExtraSection, ProjectModel


def make_model(heading: str, body: str) -> ProjectModel:
    m = ProjectModel(title="T", goal="g")
    m.extras = [ExtraSection(heading=heading, body=body)]
    return m


# --- the line shape -------------------------------------------------------------------

def test_one_id_and_a_why_is_a_record():
    assert records.keys_on_line("C7: a dev-only surface") == ["C7"]
    assert records.keys_on_line("- **UC5** — the two clauses are one goal") == ["UC5"]


def test_one_reason_may_name_every_id_it_answers():
    """The whole point of the multi-key form: two live maps wrote the SAME sentence 17 and 18 times
    in a row because a record could only carry one id."""
    assert records.keys_on_line("C101, C148, C186: an operator surface") == ["C101", "C148", "C186"]


def test_a_key_alone_is_a_dismissal_not_a_record():
    assert records.keys_on_line("C7:") == []
    assert records.keys_on_line("C7") == []


def test_prose_that_merely_starts_with_an_id_records_nothing():
    """The reason this reader is line-leading AND separator-bound: these bodies carry paragraphs
    that name other ids mid-sentence."""
    assert records.keys_on_line("C9 handles this for the gateway") == []
    assert records.keys_on_line("the gateway (C9) is a dev surface: see above") == []


def test_a_list_with_one_bad_token_records_nothing_and_is_reported():
    """A PARTIAL read is the dangerous direction — the operator believes the finding is adjudicated
    while the check goes on firing. So: all or nothing, plus a diagnostic."""
    m = make_model("Unclaimed surfaces", "C101, sea-monkeys, C186: an operator surface")
    assert records.recorded_keys(m, "Unclaimed surfaces") == set()
    assert records.malformed_records(m, "Unclaimed surfaces") == [
        "C101, sea-monkeys, C186: an operator surface"]


def test_a_well_formed_multi_key_line_is_not_reported_as_malformed():
    m = make_model("Unclaimed surfaces", "C101, C148: an operator surface")
    assert records.malformed_records(m, "Unclaimed surfaces") == []


def test_a_scoped_token_is_returned_verbatim():
    """`CAPn` and `CAPn/scope` are different judgements about one element; each caller asks for the
    token its own check honours."""
    assert records.keys_on_line("CAP4/spine — deliberately off the walk") == ["CAP4/spine"]


def test_a_directory_key_keeps_its_hyphens():
    """The bug this pins: a non-greedy path token ended at the first hyphen, so `third-party/`
    recorded `third` and silenced every sibling sharing the prefix."""
    assert records.keys_on_line("third-party/: vendored", records.DIR_KEY, records.SEP) == [
        "third-party/"]
    assert records.keys_on_line("docs - kept deliberately coarse",
                                records.DIR_KEY, records.SEP) == ["docs"]


def test_a_free_text_key_is_matched_whole_never_as_a_substring():
    """A substring test once let one adjudication silence a DIFFERENT finding."""
    lines = ["Admin pages (/orgs/:slug/admin/**): deliberate"]
    assert records.records_key(lines, "Admin pages (/orgs/:slug/admin/**)")
    assert not records.records_key(lines, "Admin pages")


# --- the heading registry -------------------------------------------------------------

def test_a_heading_that_answers_a_check_is_the_maps_build_record():
    assert records.is_maintenance("Persistence exceptions")
    assert records.is_maintenance("balance exceptions")   # matched case-insensitively, like the readers


def test_a_heading_that_describes_the_code_is_a_note():
    assert not records.is_maintenance("Entry-point coverage")
    assert not records.is_maintenance("Coverage exceptions")


def test_an_unknown_authored_heading_is_a_note():
    """Defaulting the other way would fold a hand-written section away where nobody sees it."""
    assert not records.is_maintenance("Why the scheduler is where it is")


# --- the split reaches the views ------------------------------------------------------

def make_two_section_model() -> ProjectModel:
    m = ProjectModel(title="T", goal="g")
    m.extras = [ExtraSection(heading="Persistence exceptions", body="E2: a value object."),
                ExtraSection(heading="Coverage exceptions", body="demo/: a recorded demo, not the product.")]
    return m


def test_the_graph_tells_the_viewer_which_sections_are_the_build_record():
    from coyodex.views import model_to_graph
    flags = {x["heading"]: x["maintenance"] for x in model_to_graph(make_two_section_model())["extras"]}
    assert flags == {"Persistence exceptions": True, "Coverage exceptions": False}


def test_an_id_in_authored_prose_is_resolved_against_the_MODEL_not_the_diagram():
    """The bug this pins: resolving in the browser against the diagram's node map read `R3` as the
    FOURTH role, because the Context diagram used to mint its own zero-based `R0, R1, …` actor nodes,
    whose id space collided with the model's roles."""
    from coyodex.model import Component, Role
    from coyodex.views import model_to_graph
    m = ProjectModel(title="T", goal="g")
    m.roles = [Role(id="R1", name="Tracker", kind="human", wants="x", drives="UC1"),
               Role(id="R2", name="Superadmin", kind="human", wants="y", drives="UC2"),
               Role(id="R3", name="Site visitor", kind="human", wants="z", drives="UC3")]
    m.components = [Component(id="C1", name="Reader", purpose="reads", entry_point="src/r.py:1")]
    m.extras = [ExtraSection(heading="Happy Path coverage", body="R3: no spine position. C1 reads.")]
    refs = model_to_graph(m)["extras"][0]["refs"]
    assert refs["R3"]["name"] == "Site visitor"
    assert refs["R3"]["node"] is None       # a role is not a drawn node — a name, not a link
    assert refs["C1"] == {"id": "C1", "name": "Reader", "node": "C1"}   # …a component is both


def test_an_id_the_map_does_not_define_is_left_alone():
    from coyodex.views import model_to_graph
    m = ProjectModel(title="T", goal="g")
    m.extras = [ExtraSection(heading="Balance exceptions", body="C99: long gone.")]
    assert model_to_graph(m)["extras"][0]["refs"] == {}


def test_the_markdown_puts_notes_before_the_build_record():
    """A reader scrolling the map should reach facts about their system before the adjudication log
    about the map."""
    from coyodex.views import model_to_markdown
    md = model_to_markdown(make_two_section_model())
    assert md.index("## Coverage exceptions") < md.index("Map maintenance records")
    assert md.index("Map maintenance records") < md.index("### Persistence exceptions")
    assert "E2: a value object." in md   # kept verbatim, never dropped


def test_every_element_named_in_a_committed_map_resolves_to_a_name():
    """The server half of the same rule: whatever the viewer is asked to render, the refs table must
    already know. Scanned with a DELIBERATELY BROADER pattern than `views._PROSE_ID` and filtered by
    the map's own element table, so dropping a prefix from that pattern — which is exactly how the
    role ids went unresolved — fails here instead of shipping raw ids to the screen."""
    from coyodex.model import all_elements, load_model
    from coyodex.views import model_to_graph
    repo = Path(__file__).resolve().parent.parent
    maps = [repo / ".coyodex" / "project-map.json",
            repo / "tests" / "fixtures" / "mcpolis-project-map.json",
            repo / "eval" / "fixtures" / "trapdoor" / "golden" / "project-map.json"]
    checked = 0
    for path in maps:
        if not path.is_file():
            continue
        m = load_model(path.read_text(encoding="utf-8"))
        elems = set(all_elements(m))
        for section in model_to_graph(m)["extras"]:
            named = {t for t in re.findall(r"\b[A-Z]+\d+\b", section["body"]) if t in elems}
            missing = named - set(section["refs"])
            assert not missing, f"{path.name} / {section['heading']}: unresolved {sorted(missing)}"
            checked += len(named)
    assert checked, "no committed map names an element in its extras — this gate proved nothing"


def _main() -> int:
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")
    print(f"{len(fns) - failed}/{len(fns)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_main())


def _extras(tmp):
    import os
    p = os.path.join(tmp, "extras.json")
    return p


def test_line_repeats_so_one_process_records_a_batch():
    """`_arg` read one value, so this command took one record per process: a build with 57 records
    to make spawned 57 processes, twenty of them re-typing long prose after the first attempt
    failed. They are independent appends under one heading — there was never a reason to separate
    them."""
    import json, tempfile
    from coyodex.record import main
    with tempfile.TemporaryDirectory() as tmp:
        p = _extras(tmp)
        assert main(["--map", p, "--heading", "Entry-point coverage",
                     "--line", "http-route: partial — per module",
                     "--line", "ui-route: complete — every page",
                     "--line", "cli: complete — every script entry"]) == 0
        body = json.load(open(p))["extras"][0]["body"]
        for key in ("http-route", "ui-route", "cli"):
            assert key in body, f"{key} was dropped: {body!r}"


def test_lines_from_reads_a_file_and_skips_comments_and_blanks():
    """So the lead can paste a batch together, annotate it, and hand it over as-is."""
    import json, os, tempfile
    from coyodex.record import main
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "lines.txt")
        with open(src, "w") as fh:
            fh.write("# the two Temporal kinds\njob: complete — nine schedules\n\n"
                     "poller: complete — the sweep\n")
        p = _extras(tmp)
        assert main(["--map", p, "--heading", "Entry-point coverage", "--lines-from", src]) == 0
        body = json.load(open(p))["extras"][0]["body"]
        assert "job" in body and "poller" in body
        assert "the two Temporal kinds" not in body, "a `#` comment is not a record"


def test_a_bad_line_in_a_batch_leaves_the_fragment_untouched():
    """Every line is shape-checked BEFORE anything is written. A partial append would leave the
    fragment holding some of a batch, and the caller cannot tell which without re-reading it."""
    import tempfile
    from coyodex.record import main
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(_extras(tmp))
        assert main(["--map", str(p), "--heading", "Entry-point coverage",
                     "--line", "job: complete — nine schedules"]) == 0
        before = p.read_bytes()
        assert main(["--map", str(p), "--heading", "Entry-point coverage",
                     "--line", "poller: complete — the sweep",
                     "--line", "no-why-here"]) == 2
        assert p.read_bytes() == before, "nothing may be written when any line is malformed"


def test_replace_refuses_a_batch():
    """`--replace` corrects ONE record by prefix; a batch has no single target, and guessing which
    one it meant is the silent mis-write this command exists to prevent."""
    import tempfile
    from coyodex.record import main
    with tempfile.TemporaryDirectory() as tmp:
        assert main(["--map", _extras(tmp), "--heading", "Entry-point coverage",
                     "--replace", "job", "--line", "a: x", "--line", "b: y"]) == 2


def test_every_heading_an_advisory_names_is_one_the_tools_read():
    """An advisory that says "record a line under the 'X' extras heading" while the registry does
    not know X is a trap: `record` refuses the line and the finding ships as carried with no
    escape, under a message that promised one. One shipped exactly so ('Walk jumps'), and a
    docstring went on naming a heading that had been renamed. So every heading named as an escape
    anywhere under `tools/coyodex/` must be registered — read straight off the source, so a
    renamed or newly minted heading fails here and not on a build."""
    src_dir = Path(__file__).resolve().parents[1] / "tools" / "coyodex"
    texts = {p: p.read_text(encoding="utf-8") for p in sorted(src_dir.glob("*.py"))}
    # A heading reaches an advisory either as a literal or through a `*_HEADING` constant; the
    # constants are collected first so `'{WALK_JUMPS_HEADING}' extras heading` resolves too.
    constants: dict[str, str] = {}
    for text in texts.values():
        constants.update(re.findall(r'([A-Z_]+_HEADING)\s*=\s*"([^"]+)"', text))
    named = re.compile(r"""\**['\"](?:\{(?P<const>[A-Z_]+_HEADING)\}|(?P<lit>[A-Z][A-Za-z -]{3,40}?))"""
                       r"""['\"]\**\s+extras\s+heading""")
    known = {h.lower() for h in records.KNOWN_HEADINGS}
    unknown: list[str] = []
    for path, text in texts.items():
        for hit in named.finditer(text):
            name = hit.group("lit") or constants.get(hit.group("const") or "", "")
            if name.lower() not in known:
                unknown.append(f"{path.name}:{text[: hit.start()].count(chr(10)) + 1} names "
                               f"{name or hit.group('const')!r}")
    assert not unknown, unknown


# --- the prose of a line ----------------------------------------------------------------------
# `why_of` serves the readability walk, which must count the writing and never the grammar.

def test_the_why_of_an_id_record_follows_its_keys_and_separator():
    assert records.why_of("Unclaimed surfaces", "- **C1**, C2 — an operator's own tool") == "an operator's own tool"
    assert records.why_of("Audit exceptions", "read-never-created HP4: nothing stores them") == "nothing stores them"


def test_a_free_text_key_ends_at_the_first_colon_followed_by_a_space():
    """A `path:line` key holds a colon of its own, and a quoted claim may hold one too."""
    assert records.why_of("Sweep debt", "tools/x.py:12: Plumbing, not a decision.") == "Plumbing, not a decision."
    assert records.why_of("Bucket vocabulary", "MCP protocol: the product's whole subject.") == "the product's whole subject."
    assert records.why_of("Drift exceptions", "`C3 lifecycle: created by C9`: the claim moved.") == "the claim moved."


def test_a_template_value_word_is_grammar_not_prose():
    assert records.why_of("Entry-point coverage", "cli: complete — walked every command.") == "walked every command."
    assert records.why_of("Entry-point coverage", "- http-route: partial - the eight that decide.") == "the eight that decide."
    assert records.why_of("Entry-point coverage", "cli: complete") == ""
    assert records.why_of("Balance exceptions", "security-granularity: family — one rule per family.") == "one rule per family."
    # a why that merely starts with such a word keeps it
    assert records.why_of("Entry-point coverage", "cli naming: completely covered by the stories.") == "completely covered by the stories."


def test_a_line_with_no_key_and_a_line_under_an_unknown_heading_are_returned_whole():
    assert records.why_of("Unclaimed surfaces", "  - A second sentence of the record above.") == "A second sentence of the record above."
    assert records.why_of("Notes for the next build", "cli: something a person wrote.") == "cli: something a person wrote."


def test_a_prose_line_that_merely_holds_a_colon_keeps_every_word():
    """The adversarial review's finding: under a keyed heading, a continuation sentence with a
    mid-sentence colon was split there and its first clause hidden from the counters. What stands
    before the colon must look like a key — short, no sentence punctuation, no dash."""
    prose_line = ("The operator sees two things here: the queue depth and the last error, and neither "
                  "is an interface because nobody outside asks for them")
    assert records.why_of("Unclaimed surfaces", prose_line) == prose_line
    dashed = "A note — config_loader.py reads this: the rest of the sentence"
    assert records.why_of("Unclaimed surfaces", dashed) == dashed
    ended = "It ends here. Then: a second sentence"
    assert records.why_of("Bucket vocabulary", ended) == ended
    # the longest live key is four words, and a path key's own dot is not sentence punctuation
    assert records.why_of("Bucket vocabulary", "Testing & type checking: the two gates.") == "the two gates."
    assert records.why_of("Sweep debt", "eval/retro/method.md:62: This IS a decision.") == "This IS a decision."


def test_a_quoted_claim_in_any_of_the_three_quote_styles_is_one_key_token():
    """The drift reader accepts backticks, single and double quotes around the claim, and the claim
    may hold a colon. An apostrophe inside a word opens no quote."""
    for q in ("`", "'", '"'):
        line = f"anchor-drift {q}Auth surface is protected by: org_routes.py:271{q}: the anchor is right."
        assert records.why_of("Drift exceptions", line) == "the anchor is right.", q
    assert records.why_of("Bucket vocabulary", "Bob's bucket: what Bob's tools share.") == "what Bob's tools share."


def test_a_value_word_followed_by_a_colon_or_a_paren_is_a_real_word():
    assert records.why_of("Balance exceptions", "C3: Family: the plan is billed once.") == "Family: the plan is billed once."
    assert records.why_of("Balance exceptions", "C3: family (the plan) is billed once.") == "family (the plan) is billed once."
    assert records.why_of("Entry-point coverage", "cli: Partial (see below) is the honest word.") == "Partial (see below) is the honest word."


def test_body_lines_drop_bullets_and_blank_lines():
    assert records.body_lines("- C1: a\n\n  * C2: b\n") == ["C1: a", "C2: b"]
