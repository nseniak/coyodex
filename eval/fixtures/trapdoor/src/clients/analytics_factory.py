"""Client construction for the analytics and error-reporting SaaS deps.

TRAP O3 — constructs != persists. This module BUILDS clients for Mixpanel-shaped analytics and
a Sentry-shaped error sink. It never sends an event and never writes a row. A map that records
`AnalyticsFactory emits -> Analytics` has credited the factory with its callers' traffic; the
real emit lives in `src/plugins/*/handler.py`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ClientConfig:
    """Everything needed to talk to one hosted service. Values come from the environment."""

    base_url: str
    token: str
    timeout_seconds: int = 10


class AnalyticsClient:
    """A configured, UNUSED handle. Constructing one opens no socket."""

    def __init__(self, config: ClientConfig) -> None:
        self.config = config
        self.queued: list[dict[str, str]] = []

    def enqueue(self, event: str, tenant: str) -> None:
        """Buffers in memory. The flush that actually leaves the process lives in the plugins."""
        self.queued.append({"event": event, "tenant": tenant})


class ErrorClient:
    """A configured handle for the error sink. Same story: construction, not traffic."""

    def __init__(self, config: ClientConfig) -> None:
        self.config = config


def build_analytics() -> AnalyticsClient:
    """Read config and hand back a client. No network call happens on this path."""
    return AnalyticsClient(
        ClientConfig(
            base_url=os.environ.get("ANALYTICS_URL", "https://analytics.invalid"),
            token=os.environ.get("ANALYTICS_TOKEN", ""),
        )
    )


def build_error_sink() -> ErrorClient:
    """Same shape for the error reporter."""
    return ErrorClient(
        ClientConfig(
            base_url=os.environ.get("ERRORS_URL", "https://errors.invalid"),
            token=os.environ.get("ERRORS_TOKEN", ""),
            timeout_seconds=5,
        )
    )
