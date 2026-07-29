"""Outbound channel publishing.

Traps planted here:
  M1 — `ticket.state.changed` has publishers and NO consumer anywhere in this fixture.
  M2 — the SAME channel is named twice under two spellings: the constant
       `TICKET_STATE_CHANGED = "ticket.state.changed"` here, and the literal
       `"ticket-state-changed"` used by `src/plugins/p03/handler.py`. A catalog that
       records both is the duplicated-row defect the messaging skeptics refuted most.
  M3 — no channel in this fixture carries a payload ENTITY: what goes on the wire is a
       hand-rolled dict, so a `payload` field filled with an `En` would be invented.
  M4 — `EventPublisher` reaches the broker through `_transport`, which is injected. There
       is no direct call from this component to a broker library, so a trace that emits no
       `C -> broker` backbone edge leaves the publisher wired to nothing.
"""
from __future__ import annotations

from typing import Any, Protocol

# The declaring lines for the channel names — these are the citable `source` anchors a
# messaging catalog row must use.
TICKET_STATE_CHANGED = "ticket.state.changed"
TICKET_COMMENT_ADDED = "ticket.comment.added"
ESCALATION_PAGED = "escalation.paged"


class Transport(Protocol):
    """The broker seam. Injected, so this component never names a broker library."""

    def send(self, channel: str, body: dict[str, Any]) -> None: ...


class EventPublisher:
    """Publishes ticket events. Every channel below is published; only one is consumed."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def publish_state_change(self, ticket_id: str, state: str, actor: str) -> None:
        # TRAP M1: nothing in this repo subscribes to TICKET_STATE_CHANGED.
        # TRAP M3: the body is an ad-hoc dict, not a modelled entity.
        self._transport.send(
            TICKET_STATE_CHANGED,
            {"ticket_id": ticket_id, "state": state, "actor": actor},
        )

    def publish_comment(self, ticket_id: str, comment_id: str) -> None:
        # This one IS consumed — by `src/messaging/consumer.py`.
        self._transport.send(
            TICKET_COMMENT_ADDED,
            {"ticket_id": ticket_id, "comment_id": comment_id},
        )

    def publish_page(self, ticket_id: str, rota: str) -> None:
        # Also unconsumed, and its name is used nowhere else — the plain unconsumed case,
        # so M1 has both a duplicated-spelling instance and a clean one.
        self._transport.send(ESCALATION_PAGED, {"ticket_id": ticket_id, "rota": rota})
