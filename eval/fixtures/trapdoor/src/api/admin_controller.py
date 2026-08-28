"""Operator-only HTTP handlers. These are the doors to the off-path features.

Deliberately NOT on the happy path a support agent walks: an operator reaches them directly,
and no step of the ticket story passes through here.
"""
from __future__ import annotations

from typing import Any

from src.admin.bulk_close import BulkCloseError, BulkCloser
from src.admin.export import TicketExporter
from src.auth.gate import AuthError, Principal


class AdminController:
    """Bulk close and export, the two operator actions."""

    def __init__(self, closer: BulkCloser, exporter: TicketExporter) -> None:
        self._closer = closer
        self._exporter = exporter

    def post_bulk_close(self, principal: Principal, tenant: str,
                        ticket_ids: list[str]) -> dict[str, Any]:
        """Archive a batch of resolved tickets in one operator action."""
        try:
            result = self._closer.close(principal, tenant, ticket_ids)
        except BulkCloseError as exc:
            return {"status": 400, "body": {"error": str(exc)}}
        except AuthError as exc:
            return {"status": 403, "body": {"error": str(exc)}}
        return {"status": 200, "body": result}

    def get_export(self, principal: Principal, tenant: str,
                   ticket_ids: list[str]) -> dict[str, Any]:
        """Hand the operator a CSV of the tenant's tickets."""
        try:
            document = self._exporter.to_csv(principal, tenant, ticket_ids)
        except AuthError as exc:
            return {"status": 403, "body": {"error": str(exc)}}
        return {"status": 200, "body": {"content_type": "text/csv", "document": document}}
