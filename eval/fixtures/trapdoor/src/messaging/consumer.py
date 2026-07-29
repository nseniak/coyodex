"""Inbound channel consumption — a SELF-ACTIVATED entry point.

This is the only consumer in the fixture. It runs as a background loop with no external
caller, so its `activation` is `self` and it needs a `cadence` (`continuous`) whose
`cadence_source` is the `while True` below. It also needs a `runs_in`: it runs in the
`worker` unit, never in `api`.
"""
from __future__ import annotations

from typing import Any, Callable

from src.messaging.publisher import TICKET_COMMENT_ADDED

Handler = Callable[[dict[str, Any]], None]


class CommentConsumer:
    """Drains the comment channel and fans each message out to registered handlers."""

    def __init__(self, poll_seconds: int = 5) -> None:
        self.poll_seconds = poll_seconds
        self._handlers: list[Handler] = []
        self._running = False

    def register(self, handler: Handler) -> None:
        self._handlers.append(handler)

    def handle(self, channel: str, body: dict[str, Any]) -> None:
        if channel != TICKET_COMMENT_ADDED:
            return
        for handler in self._handlers:
            handler(body)

    def run_forever(self, fetch: Callable[[], list[tuple[str, dict[str, Any]]]]) -> None:
        """The self-starting loop. Its `while True` is the cadence declaration."""
        self._running = True
        while True:  # cadence: continuous
            if not self._running:
                return
            for channel, body in fetch():
                self.handle(channel, body)

    def stop(self) -> None:
        self._running = False
