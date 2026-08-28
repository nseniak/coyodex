"""The ledger's own record type."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class LedgerEntry:
    """One month's charge against one tenant. Its own row, in the `ledger` collection."""

    id: str
    tenant: str
    period: str
    amount_cents: int
    plan: str
    posted_at: datetime | None = None
