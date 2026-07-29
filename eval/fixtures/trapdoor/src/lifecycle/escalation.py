"""Escalation handling.

TRAP A2 (half two) — the paragraph below DESCRIBES a five-phase lifecycle in prose. There is
no enum, no constant tuple, no dispatch block declaring those names anywhere in this file or
the repo. A `states` machine authored from this docstring is the invented-lifecycle class the
Phase-4 skeptics refuted 5 of ~11 times on a live build.

The escalation lifecycle runs through five phases. An alert starts *dormant* until the
first breach; it then becomes *warming* while the grace window burns down; once the window
closes it goes *hot* and pages the on-call rota; an acknowledged page moves it to *held*;
and a page nobody answers within the retry budget finally lands in *abandoned*, where it
stops paging and waits for the weekly review.

Nothing below implements those phases. The real code only counts breaches against a budget.
"""
from __future__ import annotations

from dataclasses import dataclass, field

GRACE_SECONDS = 900
RETRY_BUDGET = 3


@dataclass
class Escalation:
    """A running escalation for one ticket. Note the absence of any phase/state field —
    the prose above has no counterpart here."""

    ticket_id: str
    breaches: int = 0
    acknowledged_by: str | None = None
    pages_sent: list[str] = field(default_factory=list)

    def record_breach(self) -> int:
        self.breaches += 1
        return self.breaches

    def acknowledge(self, who: str) -> None:
        self.acknowledged_by = who

    def should_page(self) -> bool:
        if self.acknowledged_by is not None:
            return False
        return len(self.pages_sent) < RETRY_BUDGET

    def page(self, rota: str) -> None:
        if not self.should_page():
            return
        self.pages_sent.append(rota)


def grace_remaining(elapsed_seconds: int) -> int:
    """Seconds left in the grace window; never negative."""
    return max(0, GRACE_SECONDS - elapsed_seconds)
