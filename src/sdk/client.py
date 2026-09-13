"""Object-oriented SDK facade shared by Python consumers and the CLI."""

import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar
from uuid import UUID

from repoagent.adapters.sqlite.task_store import SQLiteTaskStore
from repoagent.application.tasks import TaskService
from repoagent.config import Settings
from repoagent.domain.errors import StorageError
from repoagent.domain.repository import RepositorySpec
from repoagent.domain.tasks import TaskEvent, TaskKind, TaskRecord, TaskRequest
from repoagent.ports.task_store import TaskStore

Result = TypeVar("Result")


class RepoAgent:
    """Lazy SDK client composing an application service and replaceable store.

    Construction performs no I/O. Methods return typed domain objects, including
    blocked tasks for unavailable M1 workflows. No log handlers are installed.
    SQLite connections are owned per operation; clients require no close().
    """

    def __init__(
        self, *, settings: Settings | None = None, store: TaskStore | None = None
    ) -> None:
        self._settings = (
            settings.model_copy(deep=True) if settings is not None else None
        )
        self._store = store
        self._service: TaskService | None = None

    def _run(self, operation: Callable[[TaskService], Result]) -> Result:
        try:
            if self._service is None:
                store = self._store
                if store is None:
                    settings = self._settings or Settings()
                    store = SQLiteTaskStore(settings.data_dir / "tasks.sqlite3")
                self._service = TaskService(store)
            return operation(self._service)
        except (OSError, sqlite3.Error):
            raise StorageError("Storage or filesystem operation failed") from None

    def submit(self, request: TaskRequest) -> TaskRecord:
        """Record a validated workflow request; unavailable work returns blocked."""
        return self._run(lambda service: service.submit(request))

    def get_task(self, task_id: UUID | str) -> TaskRecord:
        """Read a persisted task; raise TaskNotFound for unknown UUIDs."""
        identifier = UUID(str(task_id))
        return self._run(lambda service: service.get(identifier))

    def task_events(self, task_id: UUID | str) -> list[TaskEvent]:
        """Read public lifecycle events in sequence order."""
        identifier = UUID(str(task_id))
        return self._run(lambda service: service.events(identifier))

    def _repository_task(
        self,
        kind: TaskKind,
        source: str | Path,
        commit: str | None,
        description: str | None = None,
    ) -> TaskRecord:
        request = TaskRequest(
            kind=kind,
            repository=RepositorySpec(source=str(source), commit=commit),
            description=description,
        )
        return self.submit(request)

    def index(self, source: str | Path, *, commit: str | None = None) -> TaskRecord:
        """Request indexing (blocked until M3)."""
        return self._repository_task(TaskKind.INDEX, source, commit)

    def analyze(self, source: str | Path, *, commit: str | None = None) -> TaskRecord:
        """Request structural analysis (blocked until M2)."""
        return self._repository_task(TaskKind.ANALYZE, source, commit)

    def ask(
        self, source: str | Path, question: str, *, commit: str | None = None
    ) -> TaskRecord:
        """Request an evidence-grounded answer (blocked until M5)."""
        return self._repository_task(TaskKind.ASK, source, commit, question)

    def fix(
        self, source: str | Path, issue: str, *, commit: str | None = None
    ) -> TaskRecord:
        """Request a validated repair (blocked until M7)."""
        return self._repository_task(TaskKind.FIX, source, commit, issue)

    def test(self, source: str | Path, *, commit: str | None = None) -> TaskRecord:
        """Request isolated validation (blocked until M7)."""
        return self._repository_task(TaskKind.TEST, source, commit)

    def benchmark(self, suite: str) -> TaskRecord:
        """Request a benchmark run (blocked until M9)."""
        return self.submit(TaskRequest(kind=TaskKind.BENCHMARK, suite=suite))
