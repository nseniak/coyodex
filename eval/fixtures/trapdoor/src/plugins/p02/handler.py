"""Handler for the Microsoft Teams plugin.

Every plugin has the same three methods, differing only in the channel it listens on and the
payload it shapes. This is the flush point trap O3 refers to: the analytics client is BUILT in
`src/clients/analytics_factory.py` and USED here, so the emit edge belongs to this component.
"""
from __future__ import annotations

from typing import Any

from src.clients.analytics_factory import AnalyticsClient

CHANNEL = "notify.teams"
RETRIES = 2


class TeamsHandler:
    """Reacts to one channel and forwards a shaped payload to the analytics sink."""

    def __init__(self, analytics: AnalyticsClient) -> None:
        self._analytics = analytics
        self.seen = 0

    def accepts(self, channel: str) -> bool:
        return channel == CHANNEL

    def handle(self, body: dict[str, Any]) -> dict[str, Any]:
        """The operative emit for this plugin lives on the `enqueue` line below."""
        self.seen += 1
        payload = self.shape(body)
        self._analytics.enqueue("teams.handled", payload.get("tenant", "unknown"))
        return payload

    def shape(self, body: dict[str, Any]) -> dict[str, Any]:
        return {
            "plugin": "teams",
            "ticket_id": body.get("ticket_id", ""),
            "tenant": body.get("tenant", ""),
            "detail": body.get("state") or body.get("comment_id") or "",
        }

    def describe(self) -> str:
        return "Microsoft Teams plugin listening on " + CHANNEL
