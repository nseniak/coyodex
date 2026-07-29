"""A module whose imports outrun its code.

TRAP O4 — a dead import that tempts an unsupported edge. `ErrorClient` and `TicketState` are
imported and never used; a trace agent that reads the import block as evidence emits an edge
with no operative line behind it. `where` would have to point at the import, which the
shape-only anchor-drift pass rejects (an import cannot be the acting statement).
"""
from __future__ import annotations

from src.clients.analytics_factory import ErrorClient  # noqa: F401 — deliberately unused
from src.lifecycle.states import TicketState  # noqa: F401 — deliberately unused

RETRY_HEADER = "x-trapdoor-retry"


def next_backoff(attempt: int, base_ms: int = 250, ceiling_ms: int = 8000) -> int:
    """Exponential backoff with a ceiling. Uses nothing it imports."""
    if attempt < 0:
        raise ValueError("attempt must be non-negative")
    return min(ceiling_ms, base_ms * (2 ** attempt))


def retry_header(attempt: int) -> dict[str, str]:
    return {RETRY_HEADER: str(next_backoff(attempt))}
