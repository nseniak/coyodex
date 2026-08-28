"""The declared price list. Data, so a rule authored from it is citable."""
from __future__ import annotations

import enum


class Plan(enum.Enum):
    """The plan a tenant is on."""

    FREE = "free"
    TEAM = "team"
    ENTERPRISE = "enterprise"


#: Cents charged per ticket, by plan. The operative line for the per-ticket price rule.
PRICE_PER_TICKET: dict[Plan, int] = {
    Plan.FREE: 0,
    Plan.TEAM: 150,
    Plan.ENTERPRISE: 90,
}

#: Tickets included each month before anything is charged.
INCLUDED_TICKETS: dict[Plan, int] = {
    Plan.FREE: 25,
    Plan.TEAM: 200,
    Plan.ENTERPRISE: 2000,
}
