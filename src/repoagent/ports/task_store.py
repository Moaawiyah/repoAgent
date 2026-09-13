"""Persistence contract used by application services."""

from typing import Protocol
from uuid import UUID

from repoagent.domain.tasks import TaskEvent, TaskRecord, TaskRequest, TaskStatus


class TaskStore(Protocol):
    def create(self, request: TaskRequest) -> TaskRecord: ...

    def get(self, task_id: UUID) -> TaskRecord: ...

    def transition(
        self, task_id: UUID, status: TaskStatus, event: str, message: str
    ) -> TaskRecord: ...

    def events(self, task_id: UUID) -> list[TaskEvent]: ...
