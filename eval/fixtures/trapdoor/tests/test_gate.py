"""The write gate: who may move a ticket, and who is refused."""
from __future__ import annotations

import pytest

from src.auth.gate import WRITE_SCOPE, AuthError, Principal, require_read, require_write
from src.lifecycle.states import TicketState


def make_principal(scopes: tuple[str, ...] = (WRITE_SCOPE,), tenant: str = "acme") -> Principal:
    """Builder for a caller. Default is a writer on the acme tenant."""
    return Principal(subject="agent-1", scopes=scopes, tenant=tenant)


def test_a_writer_may_move_an_open_ticket():
    require_write(make_principal(), "acme", TicketState.TRIAGE)


def test_a_caller_without_the_write_scope_is_refused():
    with pytest.raises(AuthError):
        require_write(make_principal(scopes=()), "acme", TicketState.TRIAGE)


def test_a_caller_from_another_tenant_is_refused():
    with pytest.raises(AuthError):
        require_write(make_principal(tenant="other"), "acme", TicketState.TRIAGE)


def test_reading_a_foreign_tenant_is_refused():
    with pytest.raises(AuthError):
        require_read(make_principal(tenant="other"), "acme")
