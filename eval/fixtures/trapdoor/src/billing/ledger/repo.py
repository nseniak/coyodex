"""Writes ledger entries. This is the component that OWNS the LedgerEntry record."""
from __future__ import annotations

from typing import Any, Protocol

from src.billing.ledger.entries import LedgerEntry


class Collection(Protocol):
    def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None: ...
    def replace_one(self, query: dict[str, Any], doc: dict[str, Any], upsert: bool) -> Any: ...


class LedgerRepository:
    """The system of record for what a tenant was charged."""

    def __init__(self, entries: Collection) -> None:
        self._entries = entries

    def post(self, entry: LedgerEntry) -> None:
        """Write one month's charge. One entry per tenant per period."""
        self._entries.replace_one(
            {"tenant": entry.tenant, "period": entry.period}, self._flatten(entry), upsert=True
        )

    def load(self, tenant: str, period: str) -> LedgerEntry | None:
        doc = self._entries.find_one({"tenant": tenant, "period": period})
        return None if doc is None else self._hydrate(doc)

    def _flatten(self, entry: LedgerEntry) -> dict[str, Any]:
        return {
            "_id": entry.id, "tenant": entry.tenant, "period": entry.period,
            "amount_cents": entry.amount_cents, "plan": entry.plan, "posted_at": entry.posted_at,
        }

    def _hydrate(self, doc: dict[str, Any]) -> LedgerEntry:
        return LedgerEntry(
            id=str(doc.get("_id", "")), tenant=doc.get("tenant", ""),
            period=doc.get("period", ""), amount_cents=int(doc.get("amount_cents", 0)),
            plan=doc.get("plan", ""), posted_at=doc.get("posted_at"),
        )
