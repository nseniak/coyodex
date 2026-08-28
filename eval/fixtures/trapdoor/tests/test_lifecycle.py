"""The declared ticket lifecycle: which moves are legal, and which are refused."""
from __future__ import annotations

import pytest

from src.lifecycle.states import TRANSITIONS, TicketState, TransitionError


def test_every_state_appears_in_the_transition_table():
    assert set(TRANSITIONS) == set(TicketState)


def test_triage_may_be_accepted_or_archived():
    assert TRANSITIONS[TicketState.TRIAGE] == (TicketState.ACCEPTED, TicketState.ARCHIVED)


def test_archived_is_terminal():
    assert TRANSITIONS[TicketState.ARCHIVED] == ()


def test_resolved_may_only_be_archived():
    assert TRANSITIONS[TicketState.RESOLVED] == (TicketState.ARCHIVED,)


def test_transition_error_is_an_exception():
    assert issubclass(TransitionError, Exception)


@pytest.mark.parametrize("state", list(TicketState))
def test_no_state_lists_itself_as_a_target(state: TicketState):
    assert state not in TRANSITIONS[state]
