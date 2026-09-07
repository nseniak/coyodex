"""Tests for the countable readability checks on the map's reader-facing prose (`coyodex.prose`).

The module's whole claim is that it COUNTS rather than judges, so these tests pin the boundaries: a
20-word sentence is fine and a 21-word one is not, a backticked literal is a quotation rather than a
code name, and a summary line names a few fields and counts the rest through the shared truncation
helper instead of printing two hundred.
"""
from __future__ import annotations

from coyodex import prose
from coyodex.model import (
    BusinessRule, Component, Dep, GlossaryRow, Group, HappyStep, ProjectModel, Role, UseCase,
)


def make_sentence(words: int) -> str:
    return " ".join(["word"] * words) + "."


def make_findings(kind: str, count: int) -> list[prose.Finding]:
    return [prose.Finding(kind, f"C{n} purpose", "detail") for n in range(1, count + 1)]


def make_model() -> ProjectModel:
    """A map whose every reader-facing prose field is short, plain and self-contained."""
    m = ProjectModel(title="Demo", goal="A demo.")
    m.roles = [Role(id="R1", name="Andy", kind="human", wants="to place an order")]
    m.use_cases = [UseCase(id="UC1", name="Place order",
                           trigger_outcome="A shopper submits a basket and gets an order.")]
    m.happy_path = [HappyStep(id="HP1", uc="UC1", why="nothing precedes it")]
    m.components = [Component(id="C1", name="Checkout", purpose="Takes a basket and books an order.")]
    m.capabilities = [Group(id="CAP1", name="Ordering", purpose="Everything a shopper buys with.")]
    m.deps = [Dep(id="D1", name="Postgres", kind="datastore", used_for="Stores every order.")]
    m.rules = [BusinessRule(id="BR1", name="Owner-only cancellation",
                            statement="Only the owner of an order may cancel it.",
                            risk="A stranger could cancel another shopper's order.")]
    m.glossary = [GlossaryRow(term="basket", meaning="What a shopper has chosen but not yet paid for.")]
    return m


# --- sentence length -------------------------------------------------------------------------

def test_a_twenty_word_sentence_is_not_long_and_a_twenty_one_word_one_is() -> None:
    assert prose.long_sentences(make_sentence(20)) == []
    assert len(prose.long_sentences(make_sentence(21))) == 1


def test_each_long_sentence_in_one_field_is_reported_separately() -> None:
    text = f"{make_sentence(25)} {make_sentence(3)} {make_sentence(30)}"
    assert len(prose.long_sentences(text)) == 2


def test_the_limit_is_a_parameter_so_map_text_can_differ_from_chat() -> None:
    assert prose.long_sentences(make_sentence(12), limit=10) != []
    assert prose.long_sentences(make_sentence(12), limit=15) == []


# --- em dash ---------------------------------------------------------------------------------

def test_em_dashes_are_counted_and_a_quoted_one_is_not() -> None:
    assert prose.em_dash_count("Orders are booked — and then paid.") == 1
    assert prose.em_dash_count("It prints `a — b` verbatim.") == 0


# --- code names ------------------------------------------------------------------------------

def test_code_shapes_are_found_in_plain_text() -> None:
    assert prose.code_tokens("Reads src/order.py and books it.") == ["src/order.py"]
    # one word, one finding: the call form wins over the snake_case form inside it
    assert prose.code_tokens("Calls cancel_order() on the way out.") == ["cancel_order()"]
    assert prose.code_tokens("Pass --dry-run to preview.") == ["--dry-run"]
    assert prose.code_tokens("The order_total is recomputed.") == ["order_total"]


def test_ordinary_product_prose_names_no_code() -> None:
    assert prose.code_tokens("Only the owner of an order may cancel it.") == []
    assert prose.code_tokens("Stores every order and every payment.") == []


def test_a_backticked_literal_is_a_quotation_not_a_code_name() -> None:
    assert prose.code_tokens("The state is `in_progress` until paid.") == []


# --- bare pointers ---------------------------------------------------------------------------

def test_a_field_opening_with_a_pointer_word_is_flagged() -> None:
    assert prose.opens_with_bare_pointer("It books the order.") == "It"
    assert prose.opens_with_bare_pointer("This is the checkout.") == "This"


def test_a_pointer_word_inside_the_sentence_is_fine() -> None:
    assert prose.opens_with_bare_pointer("The checkout books it.") == ""
    assert prose.opens_with_bare_pointer("Items are priced when the shopper adds them.") == ""


# --- unresolved references (rule 4 beyond the opening pointer) -------------------------------

def test_a_split_the_box_never_names_is_flagged() -> None:
    # the sentence that motivated the rule: which two kinds? The box never says.
    assert prose.unresolved_references(
        "Mounting the MCP servers a team shares, in either kind, and keeping each one configured "
        "and running.") == ["either kind"]


def test_every_reference_shape_is_recognized() -> None:
    assert prose.unresolved_references("Configuration flows through both modes.") == ["both modes"]
    assert prose.unresolved_references("Accepts such kinds without a check.") == ["such kinds"]
    assert prose.unresolved_references("Falls back to the other way.") == ["the other way"]
    assert prose.unresolved_references("The gateway prefers the latter.") == ["the latter"]
    assert prose.unresolved_references("The former is cached.") == ["The former"]


def test_a_reference_without_a_category_noun_is_not_flagged() -> None:
    # "both servers" names WHAT the two are; only a category word ("kind", "mode") hides the split
    assert prose.unresolved_references("Restarts both servers on deploy.") == []
    assert prose.unresolved_references("The kind of MCP decides the mount.") == []


def test_alternatives_named_in_an_earlier_sentence_resolve_the_reference() -> None:
    assert prose.unresolved_references(
        "The policy check and the argument check run first. Both checks must pass.") == []


def test_the_same_sentences_own_and_is_not_an_enumeration() -> None:
    # "Opens and holds" is the sentence's clause structure, not the two transports being named
    assert prose.unresolved_references(
        "Opens and holds the live connection to each upstream, in either transport, and keeps "
        "its stored credentials valid.") == ["either transport"]


def test_two_glossary_terms_before_the_reference_resolve_it() -> None:
    text = "Serves Remote HTTP MCPs and Hosted stdio MCPs; either kind mounts the same way."
    assert prose.unresolved_references(text, ["Remote HTTP MCP", "Hosted stdio MCP"]) == []
    assert prose.unresolved_references(text, ["Remote HTTP MCP"]) == ["either kind"]


def test_a_trailing_or_enumeration_in_the_same_sentence_resolves_it() -> None:
    assert prose.unresolved_references("Runs in either mode: standalone or cloud.") == []


def test_unresolved_reference_rides_field_findings_and_the_summary() -> None:
    found = prose.field_findings("CAP2 purpose", "Mounting the shared servers, in either kind.")
    assert [f.kind for f in found] == ["unresolved reference"]
    line = prose.summarize(found)[0]
    assert line.startswith("1 prose field with an unresolved reference")
    assert "name the alternatives" in line


# --- per-field findings ----------------------------------------------------------------------

def test_a_clean_field_produces_nothing_and_an_empty_field_is_skipped() -> None:
    assert prose.field_findings("C1 purpose", "Takes a basket and books an order.") == []
    assert prose.field_findings("C1 purpose", "") == []
    assert prose.field_findings("C1 purpose", "   ") == []


def test_one_field_can_carry_several_kinds_at_once() -> None:
    text = ("It " + " ".join(["word"] * 25) + " — see src/order.py.")
    kinds = {f.kind for f in prose.field_findings("C1 purpose", text)}
    assert kinds == {"long sentence", "em dash", "code name", "bare pointer"}


def test_the_finding_names_the_field_in_readers_words_not_a_code_location() -> None:
    found = prose.field_findings("BR1 statement", "It decides.")
    assert found[0].where == "BR1 statement"


# --- summarizing -----------------------------------------------------------------------------

def test_a_summary_line_leads_with_the_count_and_carries_the_remedy() -> None:
    line = prose.summarize(make_findings("long sentence", 1))[0]
    assert line.startswith("1 prose field with a long sentence")
    assert "one idea per sentence" in line


def test_many_findings_of_one_kind_collapse_to_one_counted_line() -> None:
    lines = prose.summarize(make_findings("long sentence", 200))
    assert len(lines) == 1
    assert lines[0].startswith("200 prose fields")
    assert "+197 more" in lines[0]     # truncation goes through the shared reporting helper


def test_each_kind_gets_its_own_line_and_an_absent_kind_gets_none() -> None:
    lines = prose.summarize([*make_findings("em dash", 2), *make_findings("code name", 1)])
    assert len(lines) == 2
    assert not any("bare pointer" in line for line in lines)


# --- walking a map ---------------------------------------------------------------------------

def test_every_reader_facing_field_is_walked() -> None:
    labels = {where for where, _text in prose.iter_prose_fields(make_model())}
    assert labels == {"C1 purpose", "CAP1 purpose", "UC1 trigger/outcome", "BR1 statement",
                      "BR1 risk", "D1 used for", "R1 wants", "HP1 why", "glossary 'basket'"}


def test_a_plainly_written_map_produces_no_findings() -> None:
    assert prose.scan(prose.iter_prose_fields(make_model())) == []


def test_a_long_purpose_on_a_real_map_is_found_through_the_walk() -> None:
    m = make_model()
    m.components[0].purpose = make_sentence(30)
    found = prose.scan(prose.iter_prose_fields(m))
    assert [f.kind for f in found] == ["long sentence"]
    assert found[0].where == "C1 purpose"


# --- batching for the read fan-out ------------------------------------------------------------

def test_empty_fields_never_reach_a_batch() -> None:
    """A batch padded with blanks spends a fan-out's attention on nothing, and the count printed to
    the lead would stop being the work done."""
    batches = prose.batch_fields([("C1 purpose", "Books an order."), ("C2 purpose", "  "),
                                  ("C3 purpose", "")], cap=10)
    assert batches == [[("C1 purpose", "Books an order.")]]


def test_batches_respect_the_cap_and_keep_map_order() -> None:
    fields = [(f"C{n} purpose", f"Does thing {n}.") for n in range(1, 8)]
    batches = prose.batch_fields(fields, cap=3)
    assert [len(b) for b in batches] == [3, 3, 1]
    assert [where for b in batches for where, _t in b] == [w for w, _t in fields]


def test_a_cap_below_one_is_refused_rather_than_looping_forever() -> None:
    try:
        prose.batch_fields([("C1 purpose", "x")], cap=0)
    except ValueError:
        return
    raise AssertionError("cap=0 must raise, not produce an endless slice")


def test_the_read_prompt_asks_for_the_two_rules_a_counter_cannot_judge() -> None:
    text = prose.build_read_prompt()
    assert "UNKNOWN WORD" in text and "LOST PRECISION" in text


def test_the_read_prompt_forbids_repeating_what_is_already_counted() -> None:
    """Without this the fan-out re-reports 486 long sentences and buries its own two findings under
    a number the lead already had."""
    text = prose.build_read_prompt()
    assert "Do NOT report sentence length" in text
    for counted in ("em dash", "code name", "opening"):
        assert counted in text


# --- the six arrays this walk was blind to ----------------------------------------------------
# Both consumers read `iter_prose_fields` — the reading fan-out and the deterministic long-sentence
# gate — so a field it does not yield is a field NOTHING checks. On the 2026-08-29 mcpolis map it
# yielded 477 non-empty fields and skipped 1,171: every flow step phrase and note, every entry
# point trigger, every entity meaning, every flow title, and the whole interfaces section. Widening
# it took that map's long-sentence count from 1 to 25.

def _walked(m) -> dict[str, str]:
    from coyodex.prose import iter_prose_fields
    return {where: text for where, text in iter_prose_fields(m)}


def test_a_flow_step_phrase_and_note_are_reader_facing():
    from coyodex.model import Flow, FlowStep, ProjectModel
    m = ProjectModel(title="D", goal="g")
    m.flows = [Flow(uc="UC1", title="Sign in", steps=[
        FlowStep(n=1, src="R1", dst="C1", phrase="opens the sign-in page", note="a note")])]
    walked = _walked(m)
    assert "opens the sign-in page" in walked.values(), walked
    assert "a note" in walked.values(), walked
    assert "Sign in" in walked.values(), walked


def test_an_entry_point_trigger_and_an_entity_meaning_are_reader_facing():
    from coyodex.model import Entity, EntryPoint, ProjectModel
    m = ProjectModel(title="D", goal="g")
    m.entry_points = [EntryPoint(id="EP1", kind="http-route", trigger="a person opens the page")]
    m.entities = [Entity(id="E1", name="Token", meaning="what a headless agent signs in with")]
    vals = list(_walked(m).values())
    assert "a person opens the page" in vals, vals
    assert "what a headless agent signs in with" in vals, vals


def test_an_interfaces_what_is_reader_facing():
    """Its crossing sentences went with `interfaces[].carries[]`. What crosses is a walk step now,
    and step phrases already walk through this checker one block above."""
    from coyodex.model import Interface, ProjectModel
    m = ProjectModel(title="D", goal="g")
    m.interfaces = [Interface(id="I1", name="The gateway", what="The one address clients use.",
                              side="ours", facing="user")]
    vals = list(_walked(m).values())
    assert "The one address clients use." in vals, vals


def test_the_long_sentence_gate_now_sees_a_step_phrase():
    """The gate reads the same walk, so widening the walk widens the gate. That is the point."""
    from coyodex.model import Flow, FlowStep, ProjectModel
    from coyodex.validate_model import validate_model
    long_phrase = ("writes the answer back to the caller " + "and then " * 8 + "stops")
    m = ProjectModel(title="D", goal="g")
    m.flows = [Flow(uc="UC1", title="Sign in", steps=[
        FlowStep(n=1, src="R1", dst="C1", phrase=long_phrase)])]
    warnings = validate_model(m)[1]
    assert any("long sentence" in w for w in warnings), warnings
