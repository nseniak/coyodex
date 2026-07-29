"""HTTP surface for reading tickets.

TRAP O1 — transitive attribution. Every handler here only forwards to `TicketService`; the
external datastore call happens inside the SERVICE's repository. A map that credits this
controller with the datastore edge has attributed the edge to the wrong component. The rule:
attribute the edge to the component whose OWN code contains the operative line.

TRAP A4 — the import block below reads like a call site. `from src.clients.analytics_factory
import build_analytics` is an import, not a call; anchoring an edge at that line is drift the
shape-only anchor-drift pass must catch.
"""
from __future__ import annotations

from typing import Any

from src.auth.gate import Principal, require_read
from src.clients.analytics_factory import build_analytics  # TRAP A4: import, never called here
from src.domain.models import Ticket
from src.services.ticket_service import TicketService


class TicketReadController:
    """Read-only HTTP handlers. Owns no persistence and no external client."""

    def __init__(self, service: TicketService) -> None:
        self._service = service

    def get_ticket(self, principal: Principal, tenant: str, ticket_id: str) -> dict[str, Any]:
        require_read(principal, tenant)
        ticket = self._service.fetch(tenant, ticket_id)
        if ticket is None:
            return {"status": 404, "body": {"error": "not found"}}
        return {"status": 200, "body": self._render(ticket)}

    def list_tickets(self, principal: Principal, tenant: str, state: str | None) -> dict[str, Any]:
        require_read(principal, tenant)
        tickets = self._service.list_for_tenant(tenant, state)
        return {"status": 200, "body": [self._render(t) for t in tickets]}

    def get_comments(self, principal: Principal, tenant: str, ticket_id: str) -> dict[str, Any]:
        require_read(principal, tenant)
        ticket = self._service.fetch(tenant, ticket_id)
        if ticket is None:
            return {"status": 404, "body": {"error": "not found"}}
        return {"status": 200, "body": [{"id": c.id, "text": c.text} for c in ticket.comments]}

    def _render(self, ticket: Ticket) -> dict[str, Any]:
        return {
            "id": ticket.id,
            "title": ticket.title,
            "state": ticket.state.value,
            "assignee": ticket.assignee,
            "comment_count": len(ticket.comments),
        }
