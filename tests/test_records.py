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
