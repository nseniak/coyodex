"""Persistence for tickets.

TRAP A3 — the entity `Ticket` is DEFINED in `src/domain/models.py`, but the write that makes
this component its system of record is the `replace_one` line below. A grounding skeptic asked
"where is Ticket stored?" reports the DEFINITION line (it is the only place the type appears
by name), and `anchor-drift` then reads that as drift against the stored write anchor. On one
live map 9 of 13 drift findings were exactly this shape, and the lead hand-wrote a filter
script to strip them.

TRAP P2 — this component also writes to the `search_index` container, which no entity names.
"""
from __future__ import annotations

from typing import Any, Protocol

from src.domain.models import Attachment, Comment, LockDoc, Ticket
from src.lifecycle.states import TicketState


class Collection(Protocol):
    """The narrow slice of a document-store collection this repository needs."""

    def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None: ...
    def replace_one(self, query: dict[str, Any], doc: dict[str, Any], upsert: bool) -> Any: ...
    def delete_one(self, query: dict[str, Any]) -> Any: ...


class TicketRepository:
    """The system of record for `Ticket`, `Comment` and `Attachment`."""

    def __init__(self, tickets: Collection, locks: Collection, search_index: Collection) -> None:
        self._tickets = tickets
        self._locks = locks
        # TRAP P2: a real container this fixture's domain model never names as an entity store.
        self._search_index = search_index

    def load(self, ticket_id: str) -> Ticket | None:
        doc = self._tickets.find_one({"_id": ticket_id})
        if doc is None:
            return None
        return self._hydrate(doc)

    def save(self, ticket: Ticket) -> None:
        """The operative write. THIS line is the honest anchor for `C persists Ticket`."""
        doc = self._flatten(ticket)
        self._tickets.replace_one({"_id": ticket.id}, doc, upsert=True)

    def index(self, ticket: Ticket) -> None:
        """Secondary write into a container no entity records as its store (trap P2)."""
        self._search_index.replace_one(
            {"_id": ticket.id},
            {"title": ticket.title, "body": ticket.body, "tenant": ticket.tenant},
            upsert=True,
        )

    def acquire_lock(self, lock: LockDoc) -> None:
        """Infra-only write — the `Persistence exceptions` escape exists for exactly this."""
        self._locks.replace_one({"_id": lock.key}, {"holder": lock.holder}, upsert=True)

    def release_lock(self, key: str) -> None:
        self._locks.delete_one({"_id": key})

    # ---- mapping helpers (no persistence happens below this line) --------------------

    def _hydrate(self, doc: dict[str, Any]) -> Ticket:
        comments = [
            Comment(
                id=c["id"],
                ticket_id=doc["_id"],
                author=c["author"],
                text=c["text"],
                attachments=[
                    Attachment(
                        id=a["id"],
                        comment_id=c["id"],
                        filename=a["filename"],
                        object_key=a["object_key"],
                        size_bytes=a["size_bytes"],
                    )
                    for a in c.get("attachments", [])
                ],
            )
            for c in doc.get("comments", [])
        ]
        return Ticket(
            id=doc["_id"],
            tenant=doc["tenant"],
            title=doc["title"],
            body=doc["body"],
            state=TicketState(doc["state"]),
            reporter=doc["reporter"],
            assignee=doc.get("assignee"),
            comments=comments,
        )

    def _flatten(self, ticket: Ticket) -> dict[str, Any]:
        return {
            "_id": ticket.id,
            "tenant": ticket.tenant,
            "title": ticket.title,
            "body": ticket.body,
            "state": ticket.state.value,
            "reporter": ticket.reporter,
            "assignee": ticket.assignee,
            "comments": [
                {
                    "id": c.id,
                    "author": c.author,
                    "text": c.text,
                    "attachments": [
                        {
                            "id": a.id,
                            "filename": a.filename,
                            "object_key": a.object_key,
                            "size_bytes": a.size_bytes,
                        }
                        for a in c.attachments
                    ],
                }
                for c in ticket.comments
            ],
        }
