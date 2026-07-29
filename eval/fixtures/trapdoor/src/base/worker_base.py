"""The shared background-worker base class.

TRAP D1 — this base class is never itself deployed. Its ONLY concrete subclass,
`ReportWorker`, runs in the `worker` unit (see `docker-compose.yml`). A map that tags the
subclass with `runs_in: [worker]` but leaves the base untagged draws the base class as
unplaced, even though every line of it executes inside the worker process. validate's
inheritance/`runs_in` check exists for this: an `extends` edge whose child is placed and whose
parent is not.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass
class WorkerResult:
    """What one worker pass produced."""

    processed: int
    failed: int
    note: str = ""


class WorkerBase(abc.ABC):
    """Template method for every background worker in the fixture."""

    #: How long a subclass may run before the supervisor considers it stuck.
    budget_seconds: int = 120

    def __init__(self, name: str) -> None:
        self.name = name
        self.passes = 0

    def run_once(self) -> WorkerResult:
        """The template: prepare, do the subclass's work, then record."""
        self.before()
        result = self.work()
        self.passes += 1
        self.after(result)
        return result

    def before(self) -> None:
        """Hook — subclasses may override."""

    def after(self, result: WorkerResult) -> None:
        """Hook — subclasses may override."""

    @abc.abstractmethod
    def work(self) -> WorkerResult:
        """The subclass's actual pass."""
        raise NotImplementedError
