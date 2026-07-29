"""The ONE real, declared lifecycle in this fixture.

TRAP A2 (half one) — a `states` machine authored from this enum is grounded: every state
name below is a name this file literally contains, and `validate --check-sources` can verify
it. Its sibling `escalation.py` describes a second lifecycle in PROSE only; a machine
authored from that docstring is invented and must be refuted.
"""
from __future__ import annotations

import enum


class TicketState(enum.Enum):
    """Declared ticket lifecycle. This block is the citable `source` for a states machine."""

    TRIAGE = "triage"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ARCHIVED = "archived"


# The legal transitions, declared as data so the dispatch is readable and citable.
TRANSITIONS: dict[TicketState, tuple[TicketState, ...]] = {
    TicketState.TRIAGE: (TicketState.ACCEPTED, TicketState.ARCHIVED),
    TicketState.ACCEPTED: (TicketState.IN_PROGRESS, TicketState.ARCHIVED),
    TicketState.IN_PROGRESS: (TicketState.RESOLVED,),
    TicketState.RESOLVED: (TicketState.ARCHIVED,),
    TicketState.ARCHIVED: (),
}


class TransitionError(Exception):
    """Raised when a caller asks for a transition the table does not allow."""


def advance(current: TicketState, target: TicketState) -> TicketState:
    """Move a ticket along the declared lifecycle, or refuse."""
    allowed = TRANSITIONS.get(current, ())
    if target not in allowed:
        raise TransitionError(f"{current.value} -> {target.value} is not a legal transition")
    return target


def is_terminal(state: TicketState) -> bool:
    """A state with no outgoing transition ends the lifecycle."""
    return not TRANSITIONS.get(state, ())
