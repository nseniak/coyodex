"""Close many tickets at once. An operator action, off the normal walk."""
from __future__ import annotations

from src.auth.gate import Principal, require_write
from src.lifecycle.states import TicketState
from src.services.ticket_service import TicketService


class BulkCloseError(Exception):
    """Raised when a bulk close is asked for more tickets than one run may touch."""


#: The most tickets one bulk close may move. Above this the operator must split the work.
MAX_BATCH = 500


class BulkCloser:
    """Moves a batch of resolved tickets to archived in one operator action."""

    def __init__(self, service: TicketService) -> None:
        self._service = service

    def close(self, principal: Principal, tenant: str, ticket_ids: list[str]) -> dict[str, int]:
        """Archive every resolved ticket in the batch. Reports what moved and what did not."""
        if len(ticket_ids) > MAX_BATCH:
            raise BulkCloseError(f"{len(ticket_ids)} tickets asked for; {MAX_BATCH} is the limit")
        moved = 0
        skipped = 0
        for ticket_id in ticket_ids:
            ticket = self._service.fetch(tenant, ticket_id)
            if ticket is None or ticket.state is not TicketState.RESOLVED:
                skipped += 1
                continue
            require_write(principal, tenant, ticket.state)
            self._service.transition(ticket, TicketState.ARCHIVED, principal.subject)
            moved += 1
        return {"moved": moved, "skipped": skipped}
