"""Turns a ticket count into an amount owed."""
from __future__ import annotations

from src.billing.pricing.plan_table import INCLUDED_TICKETS, PRICE_PER_TICKET, Plan


class PriceError(Exception):
    """Raised when a caller asks to price a month that cannot be priced."""


def billable_tickets(plan: Plan, raised: int) -> int:
    """Tickets above the plan's included allowance. Never negative."""
    if raised < 0:
        raise PriceError("a month cannot have a negative ticket count")
    return max(0, raised - INCLUDED_TICKETS[plan])


def month_total_cents(plan: Plan, raised: int) -> int:
    """What the tenant owes for one month, in cents."""
    return billable_tickets(plan, raised) * PRICE_PER_TICKET[plan]
