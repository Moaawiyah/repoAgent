"""Lazy task service composition and storage error translation."""

import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from repoagent.adapters.sqlite.task_store import SQLiteTaskStore
from repoagent.application.tasks import TaskService
from repoagent.config import Settings
from repoagent.domain.errors import StorageError
from repoagent.domain.repository import RepositorySpec
from repoagent.domain.tasks import TaskKind, TaskRecord, TaskRequest
from repoagent.ports.task_store import TaskStore

Result = TypeVar("Result")


class TaskApi:
    def __init__(self, settings: Settings | None, store: TaskStore | None) -> None:
        self._settings, self._store = settings, store
        self._service: TaskService | None = None

    def run(self, operation: Callable[[TaskService], Result]) -> Result:
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

    def repository_task(
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
        return self.run(lambda service: service.submit(request))
