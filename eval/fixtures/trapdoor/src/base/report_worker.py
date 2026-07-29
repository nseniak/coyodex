"""The one concrete worker — a SELF-ACTIVATED entry point running in the `worker` unit.

Pairs with `worker_base.py` for trap D1: this class is placed (`runs_in: [worker]`), its base
class is not, and every line of the base executes here.
"""
from __future__ import annotations

from src.base.worker_base import WorkerBase, WorkerResult
from src.lifecycle.states import TicketState
from src.store.ticket_repo import TicketRepository

#: Cron expression the supervisor reads. This line is the `cadence_source`.
SCHEDULE = "*/15 * * * *"


class ReportWorker(WorkerBase):
    """Sweeps resolved tickets and produces a rollup. Runs on the schedule above."""

    def __init__(self, repo: TicketRepository, tenants: list[str]) -> None:
        super().__init__("report-worker")
        self._repo = repo
        self._tenants = tenants
        self.last_rollup: dict[str, int] = {}

    def work(self) -> WorkerResult:
        processed = 0
        failed = 0
        rollup: dict[str, int] = {}
        for tenant in self._tenants:
            for n in range(1, 4):
                ticket = self._repo.load(f"{tenant}-{n}")
                if ticket is None:
                    failed += 1
                    continue
                processed += 1
                if ticket.state is TicketState.RESOLVED:
                    rollup[tenant] = rollup.get(tenant, 0) + 1
        self.last_rollup = rollup
        return WorkerResult(processed=processed, failed=failed, note="rollup")

    def after(self, result: WorkerResult) -> None:
        if result.failed:
            self.budget_seconds = min(600, self.budget_seconds * 2)
