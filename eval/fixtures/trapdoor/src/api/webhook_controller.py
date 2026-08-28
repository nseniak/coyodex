"""Sends a ticket event out to the tenant's own endpoint.

The one handler in this fixture whose work leaves the process. It is called from the ticket
write path, so the feature that moves a ticket is also the feature that reaches out.
"""
from __future__ import annotations

from typing import Any

from src.domain.models import Ticket
from src.notify.webhook_sender import DeliveryError, WebhookSender


class WebhookNotifier:
    """Announces a state change to whoever the tenant told us to tell."""

    def __init__(self, sender: WebhookSender) -> None:
        self._sender = sender

    def announce_transition(self, ticket: Ticket) -> dict[str, Any]:
        """Tell the tenant's endpoint that a ticket moved. Failure is reported, never raised."""
        try:
            status = self._sender.deliver("ticket.transitioned", {
                "ticket_id": ticket.id, "tenant": ticket.tenant, "state": ticket.state.value,
            })
        except DeliveryError as exc:
            return {"delivered": False, "reason": str(exc)}
        return {"delivered": True, "status": status}
