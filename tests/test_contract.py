"""Tests for `coyodex contract <name>` — the verb that hands an agent its half of a contract.

The bug this verb exists to remove was silent: a build filled the skeptic template with one text
replacement and sent the whole file, so ten skeptics received the LEAD's instructions as their own
and four were told to read a claims file that does not exist. Nothing in the map or the gates could
see it. So the tests below pin the boundary itself, in both template shapes, and pin that no
lead-facing sentence survives into what an agent receives.
"""
from __future__ import annotations

import io
import contextlib
from pathlib import Path

from coyodex import contract

REPO_ROOT = Path(__file__).resolve().parent.parent

# Sentences that exist ONLY to instruct the lead. Any one of them in a rendered contract means the
# header crossed the boundary — the exact failure a real build paid for.
_LEAD_ONLY = ("Copy this file", "do not retype it from prose", "instructions to you, the",
              "Everything below the line is what the agent reads")


def make_quoted_template() -> str:
    return ("# Title\n\nLead instructions here.\n\n> You are an agent.\n>\n> Do the thing.\n")


def make_plain_template() -> str:
    return ("# Title\n\nLead instructions here.\n\n---\n\nYou are an agent.\n\nDo the thing.\n")


def render(name: str) -> str:
    return contract.render(name, REPO_ROOT)


# --- the boundary, both shapes -----------------------------------------------------------------

def test_a_quoted_template_yields_its_block_with_the_marker_stripped() -> None:
    assert contract.agent_half(make_quoted_template()) == "You are an agent.\n\nDo the thing."


def test_a_plain_template_yields_everything_after_its_divider() -> None:
    assert contract.agent_half(make_plain_template()) == "You are an agent.\n\nDo the thing."


def test_a_template_with_no_boundary_raises_rather_than_handing_over_the_header() -> None:
    """Silently returning the whole file is the failure this verb exists to remove, so the
    no-boundary case must be loud."""
    try:
        contract.agent_half("# Title\n\nLead instructions only.\n")
    except ValueError as exc:
        assert "no agent boundary" in str(exc)
        return
    raise AssertionError("a template with no boundary must raise")


def test_two_dividers_are_ambiguous_and_refused() -> None:
    try:
        contract.agent_half("# T\n\n---\n\nmiddle\n\n---\n\nagent\n")
    except ValueError as exc:
        assert "ambiguous" in str(exc)
        return
    raise AssertionError("two dividers must raise rather than guess which one is the boundary")


# --- the real templates ------------------------------------------------------------------------

def test_every_real_contract_renders_and_starts_with_the_agents_own_words() -> None:
    for name in contract.CONTRACTS:
        text = render(name)
        assert text.strip(), f"{name} rendered empty"
        assert text.lstrip().startswith("You are"), (
            f"{name} does not open by addressing the agent — the boundary is in the wrong place")


def test_no_lead_facing_sentence_survives_into_any_rendered_contract() -> None:
    for name in contract.CONTRACTS:
        text = render(name)
        leaked = [phrase for phrase in _LEAD_ONLY if phrase in text]
        assert not leaked, f"{name} leaks lead-only text {leaked} into the agent's prompt"


def test_no_quote_marker_survives_into_a_rendered_contract() -> None:
    """A `> ` left on every line is how an agent learns it was handed a document rather than a
    brief; it also breaks the fenced JSON examples the contracts carry."""
    for name in contract.CONTRACTS:
        stray = [line for line in render(name).splitlines() if line.startswith(">")]
        assert not stray, f"{name} still carries {len(stray)} quoted line(s)"


# --- the writing rules ride along, but only where they can be acted on --------------------------

def test_the_authoring_contracts_carry_the_writing_rules() -> None:
    for name in sorted(contract.AUTHORING):
        assert "One idea per sentence" in render(name), (
            f"{name} agents author reader-facing prose and received no writing rule")


def test_the_other_contracts_do_not_pay_for_rules_they_cannot_act_on() -> None:
    for name in set(contract.CONTRACTS) - contract.AUTHORING:
        assert "One idea per sentence" not in render(name), (
            f"{name} agents author no reader-facing prose; the rules are prompt weight there")


# --- the command line ----------------------------------------------------------------------------

def test_an_unknown_contract_name_is_refused_with_the_valid_set() -> None:
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        assert contract.main(["nonsense"]) == 2
    assert "unknown contract" in err.getvalue()


def test_no_argument_prints_usage_and_fails_so_a_typo_is_never_silent() -> None:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert contract.main([]) == 2
    assert "usage: coyodex contract" in out.getvalue()


def test_the_verb_prints_the_contract_to_stdout() -> None:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert contract.main(["skeptic"]) == 0
    assert out.getvalue().lstrip().startswith("You are a fresh-context skeptic")
