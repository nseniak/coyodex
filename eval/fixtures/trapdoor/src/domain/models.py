"""The domain model.

Traps planted here:
  P1 — `AuditEntry` is written by nobody in this fixture's edge list, so it lands in
       validate's "Entities with no owning component" advisory, which offers NO recordable
       escape token. Three live leads independently invented a `Persistence exceptions`
       heading for it; that heading exists now but is read by a DIFFERENT rule.
  P3 — `Ticket`/`Comment`/`Attachment` need authored E<->E relations; a map that only emits
       C->E edges leaves the entity graph disconnected.
  A3 — `Ticket` is DEFINED here but WRITTEN in `src/store/ticket_repo.py`; a claim anchored
       at this class definition is the anchor-drift store false positive.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from src.lifecycle.states import TicketState


@dataclass
class Ticket:
    """A unit of work raised by a reporter and worked by an assignee.

    Stored in the `tickets` collection of the primary datastore. The class body is the
    DEFINITION; the write happens in the repository, several files away.
    """

    id: str
    tenant: str
    title: str
    body: str
    state: TicketState
    reporter: str
    assignee: str | None = None
    created_at: datetime | None = None
    comments: list["Comment"] = field(default_factory=list)


@dataclass
class Comment:
    """A note appended to a ticket. Composed into its ticket (embedded, not its own row)."""

    id: str
    ticket_id: str
    author: str
    text: str
    attachments: list["Attachment"] = field(default_factory=list)


@dataclass
class Attachment:
    """A file hung off a comment. Its bytes live in object storage; only the pointer is here."""

    id: str
    comment_id: str
    filename: str
    object_key: str
    size_bytes: int


@dataclass
class AuditEntry:
    """An immutable record of a state change.

    TRAP P1: nothing in this fixture persists it. The append happens through the generic
    plugin bus, so no component carries a `persists`/`writes` C->E edge to it, and validate's
    "Entities with no owning component" advisory fires with no way to record the decision.
    """

    id: str
    ticket_id: str
    actor: str
    from_state: str
    to_state: str
    at: datetime | None = None


@dataclass
class LockDoc:
    """An advisory lock row. Infra-only: written by the repository, named by no use case.

    This one DOES have a recordable escape (`Persistence exceptions` accepts a `Cn`), which
    makes it the control that shows P1's gap is about the OTHER advisory.
    """

    key: str
    holder: str
    expires_at: datetime | None = None
