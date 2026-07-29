"""Ticket use-case orchestration — the component that really owns the datastore edge.

This is the honest destination of trap O1: `TicketReadController` and `TicketWriteController`
both forward here, and the operative datastore statements live in the repository this service
holds. The edge `TicketService -> TicketRepository` is real; `Controller -> Datastore` is not.
"""
from __future__ import annotations

from src.domain.models import Comment, LockDoc, Ticket
from src.lifecycle.states import TicketState, advance
from src.messaging.publisher import EventPublisher
from src.store.ticket_repo import TicketRepository


class TicketService:
    """Application logic for the ticket lifecycle."""

    def __init__(self, repo: TicketRepository, publisher: EventPublisher) -> None:
        self._repo = repo
        self._publisher = publisher

    def fetch(self, tenant: str, ticket_id: str) -> Ticket | None:
        ticket = self._repo.load(ticket_id)
        if ticket is None or ticket.tenant != tenant:
            return None
        return ticket

    def list_for_tenant(self, tenant: str, state: str | None) -> list[Ticket]:
        # A deliberately naive listing: the fixture has no query layer, and the point of this
        # component is edge ownership, not query performance.
        found: list[Ticket] = []
        for ticket_id in self._known_ids(tenant):
            ticket = self._repo.load(ticket_id)
            if ticket is None:
                continue
            if state is not None and ticket.state.value != state:
                continue
            found.append(ticket)
        return found

    def transition(self, ticket: Ticket, target: TicketState, actor: str) -> Ticket:
        """Move a ticket and announce it. The announce is a channel publish (traps M1/M2)."""
        ticket.state = advance(ticket.state, target)
        self._repo.save(ticket)
        self._repo.index(ticket)
        self._publisher.publish_state_change(ticket.id, ticket.state.value, actor)
        return ticket

    def comment(self, ticket: Ticket, comment: Comment) -> Ticket:
        ticket.comments.append(comment)
        self._repo.save(ticket)
        return ticket

    def with_lock(self, key: str, holder: str) -> LockDoc:
        lock = LockDoc(key=key, holder=holder)
        self._repo.acquire_lock(lock)
        return lock

    def _known_ids(self, tenant: str) -> list[str]:
        # Stand-in for a real index scan; kept trivial on purpose.
        return [f"{tenant}-{n}" for n in range(1, 4)]
