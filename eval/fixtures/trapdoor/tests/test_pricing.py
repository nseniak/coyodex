"""What a tenant owes: the allowance, then the per-ticket price."""
from __future__ import annotations

import pytest

from src.billing.pricing.calculator import PriceError, billable_tickets, month_total_cents
from src.billing.pricing.plan_table import INCLUDED_TICKETS, PRICE_PER_TICKET, Plan


def make_plan(name: str = "team") -> Plan:
    """Builder, so a test names the plan it means rather than the enum member."""
    return Plan(name)


def test_a_month_inside_the_allowance_costs_nothing():
    assert month_total_cents(make_plan(), INCLUDED_TICKETS[Plan.TEAM]) == 0


def test_tickets_above_the_allowance_are_billable():
    assert billable_tickets(make_plan(), INCLUDED_TICKETS[Plan.TEAM] + 10) == 10


def test_the_free_plan_never_charges():
    assert month_total_cents(make_plan("free"), 10_000) == 0


def test_enterprise_is_cheaper_per_ticket_than_team():
    assert PRICE_PER_TICKET[Plan.ENTERPRISE] < PRICE_PER_TICKET[Plan.TEAM]


def test_a_negative_month_is_refused():
    with pytest.raises(PriceError):
        billable_tickets(make_plan(), -1)


def test_every_plan_has_both_a_price_and_an_allowance():
    assert set(PRICE_PER_TICKET) == set(Plan) == set(INCLUDED_TICKETS)
