"""Write a tenant's tickets out as CSV. An operator action, off the normal walk."""
from __future__ import annotations

import csv
import io

from src.auth.gate import Principal, require_read
from src.store.ticket_repo import TicketRepository

#: The columns the export writes, in order. Changing this changes a file people keep.
COLUMNS = ("id", "tenant", "title", "state", "reporter", "assignee")


class TicketExporter:
    """Renders tickets as a CSV document the operator downloads."""

    def __init__(self, repo: TicketRepository) -> None:
        self._repo = repo

    def to_csv(self, principal: Principal, tenant: str, ticket_ids: list[str]) -> str:
        """Every ticket the caller may read, as one CSV document."""
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(COLUMNS)
        for ticket_id in ticket_ids:
            ticket = self._repo.load(ticket_id)
            if ticket is None or ticket.tenant != tenant:
                continue
            require_read(principal, tenant)
            writer.writerow([
                ticket.id, ticket.tenant, ticket.title, ticket.state.value,
                ticket.reporter, ticket.assignee or "",
            ])
        return buffer.getvalue()
