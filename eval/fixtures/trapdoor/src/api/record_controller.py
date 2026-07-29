"""Write surface for tickets.

TRAP O2 — ownership overclaim. This controller CALLS `.save()`, so it reads like the system of
record for `Ticket`. It is not: the operative `replace_one` lives in `TicketRepository`. On a
live build this shape produced 5 of 40 refuted dependency claims. The correct map says
`TicketRepository persists Ticket`; this controller only `reads` it.
"""
from __future__ import annotations

from typing import Any

from src.auth.gate import Principal, require_write
from src.domain.models import Comment, Ticket
from src.lifecycle.states import TicketState
from src.services.ticket_service import TicketService


class TicketWriteController:
    """Mutating HTTP handlers. Holds no collection and issues no store call of its own."""

    def __init__(self, service: TicketService) -> None:
        self._service = service

    def post_transition(self, principal: Principal, tenant: str, ticket_id: str,
                        target: str) -> dict[str, Any]:
        ticket = self._service.fetch(tenant, ticket_id)
        if ticket is None:
            return {"status": 404, "body": {"error": "not found"}}
        require_write(principal, tenant, ticket.state)
        moved = self._service.transition(ticket, TicketState(target), principal.subject)
        return {"status": 200, "body": {"id": moved.id, "state": moved.state.value}}

    def post_comment(self, principal: Principal, tenant: str, ticket_id: str,
                     text: str) -> dict[str, Any]:
        ticket = self._service.fetch(tenant, ticket_id)
        if ticket is None:
            return {"status": 404, "body": {"error": "not found"}}
        require_write(principal, tenant, ticket.state)
        comment = Comment(
            id=f"{ticket_id}-c{len(ticket.comments) + 1}",
            ticket_id=ticket_id,
            author=principal.subject,
            text=text,
        )
        # `.save()` is reached from here, but it is the SERVICE that calls the repository and
        # the REPOSITORY that issues the write. Reading this line as ownership is the overclaim.
        updated = self._service.comment(ticket, comment)
        return {"status": 201, "body": {"comments": len(updated.comments)}}

    def post_lock(self, principal: Principal, tenant: str, key: str) -> dict[str, Any]:
        require_write(principal, tenant, TicketState.TRIAGE)
        lock = self._service.with_lock(key, principal.subject)
        return {"status": 200, "body": {"key": lock.key, "holder": lock.holder}}

    def _summary(self, ticket: Ticket) -> dict[str, Any]:
        return {"id": ticket.id, "state": ticket.state.value}
