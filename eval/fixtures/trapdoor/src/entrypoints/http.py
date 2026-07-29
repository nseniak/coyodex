"""The `api` unit's process entry point — externally activated HTTP routes.

The compose `api` service runs `python -m src.entrypoints.http`, so every route registered
here `runs_in: ["api"]`. This is the fixture's whole external entry surface on the Python side;
`web/src/components/` is the browser half.
"""
from __future__ import annotations

from typing import Any, Callable

from src.api.passthrough_controller import TicketReadController
from src.api.record_controller import TicketWriteController
from src.auth.gate import Principal

Route = Callable[..., dict[str, Any]]


class Router:
    """A minimal route table. The registrations below ARE the entry-point inventory."""

    def __init__(self) -> None:
        self.routes: dict[tuple[str, str], Route] = {}

    def add(self, method: str, path: str, handler: Route) -> None:
        self.routes[(method, path)] = handler

    def dispatch(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        handler = self.routes.get((method, path))
        if handler is None:
            return {"status": 404, "body": {"error": "no route"}}
        return handler(**kwargs)


def build_router(read: TicketReadController, write: TicketWriteController) -> Router:
    """Register every externally-activated route. Grep target for the front-door check."""
    router = Router()
    router.add("GET", "/tickets/{id}", read.get_ticket)
    router.add("GET", "/tickets", read.list_tickets)
    router.add("GET", "/tickets/{id}/comments", read.get_comments)
    router.add("POST", "/tickets/{id}/transition", write.post_transition)
    router.add("POST", "/tickets/{id}/comments", write.post_comment)
    router.add("POST", "/locks/{key}", write.post_lock)
    return router


def anonymous(tenant: str) -> Principal:
    """Used by the health route, which needs no scopes."""
    return Principal(subject="anonymous", scopes=(), tenant=tenant)
