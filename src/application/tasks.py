"""Application task service; transport-independent M1 capability handling."""

import logging
from uuid import UUID

from repoagent.domain.tasks import (
    TaskEvent,
    TaskKind,
    TaskRecord,
    TaskRequest,
    TaskStatus,
)
from repoagent.ports.task_store import TaskStore

CAPABILITIES = {
    TaskKind.INDEX: "M10 (task orchestration; indexing exists via repoagent index)",
    TaskKind.ANALYZE: "M2 (repository ingestion and AST analysis)",
    TaskKind.ASK: "M5 (retrieval-grounded investigation)",
    TaskKind.FIX: "M7 (M6 patch generation, then M7 isolated validation)",
    TaskKind.TEST: "M7 (isolated validation)",
    TaskKind.BENCHMARK: "M9 (evaluation framework)",
}


class TaskService:
    def __init__(self, store: TaskStore) -> None:
        self.store = store

    def submit(self, request: TaskRequest) -> TaskRecord:
        task = self.store.create(request)
        message = (
            f"{request.kind} is unavailable in M1; "
            f"requires {CAPABILITIES[request.kind]}"
        )
        task = self.store.transition(
            task.id, TaskStatus.BLOCKED, "capability_unavailable", message
        )
        logging.getLogger("repoagent").info(
            "Task blocked",
            extra={
                "event": "capability_unavailable",
                "task_id": task.id,
                "kind": request.kind,
                "status": task.status,
            },
        )
        return task

    def get(self, task_id: UUID) -> TaskRecord:
        return self.store.get(task_id)

    def events(self, task_id: UUID) -> list[TaskEvent]:
        return self.store.events(task_id)
