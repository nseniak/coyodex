"""The `worker` unit's process entry point — SELF-activated only.

The compose `worker` service runs `python -m src.entrypoints.worker`. Two self-starting entry
points live behind it: `ReportWorker` on its cron schedule and `CommentConsumer` on its
continuous loop. Neither has an external caller, so neither needs a use case to claim it.
"""
from __future__ import annotations

from src.base.report_worker import SCHEDULE, ReportWorker
from src.messaging.consumer import CommentConsumer


def build_consumer() -> CommentConsumer:
    """The continuous drain. `runs_in: ["worker"]`."""
    return CommentConsumer(poll_seconds=5)


def schedule_of(worker: ReportWorker) -> str:
    """The cron cadence the supervisor reads for `worker`."""
    return SCHEDULE


def supervise(worker: ReportWorker, consumer: CommentConsumer, passes: int) -> int:
    """A tiny supervisor loop, kept synchronous so the fixture stays readable."""
    done = 0
    for _ in range(passes):
        result = worker.run_once()
        done += result.processed
        if result.failed > 3:
            consumer.stop()
            break
    return done
