"""Durable task records and atomic, ordered lifecycle events."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from repoagent.adapters.sqlite.database import connect, initialize
from repoagent.domain.errors import InvalidTransition, TaskNotFound
from repoagent.domain.tasks import TaskEvent, TaskRecord, TaskRequest, TaskStatus

TRANSITIONS = {
    TaskStatus.PENDING: {TaskStatus.RUNNING, TaskStatus.BLOCKED, TaskStatus.FAILED},
    TaskStatus.RUNNING: {
        TaskStatus.SUCCEEDED,
        TaskStatus.BLOCKED,
        TaskStatus.FAILED,
    },
    TaskStatus.BLOCKED: set(),
    TaskStatus.SUCCEEDED: set(),
    TaskStatus.FAILED: set(),
}


class SQLiteTaskStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        initialize(path)

    def create(self, request: TaskRequest) -> TaskRecord:
        task = TaskRecord(request=request)
        event = TaskEvent(
            task_id=task.id,
            sequence=1,
            name="task_created",
            status=task.status,
            timestamp=task.created_at,
            message="Task recorded",
        )
        with connect(self.path) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO tasks VALUES (?, ?)",
                (str(task.id), task.model_dump_json()),
            )
            connection.execute(
                "INSERT INTO events VALUES (?, ?, ?)",
                (str(task.id), 1, event.model_dump_json()),
            )
        return task

    def get(self, task_id: UUID) -> TaskRecord:
        with connect(self.path) as connection:
            row = connection.execute(
                "SELECT record FROM tasks WHERE id = ?", (str(task_id),)
            ).fetchone()
        if row is None:
            raise TaskNotFound(f"Task not found: {task_id}")
        return TaskRecord.model_validate_json(
            row["record"], context={"persisted": True}
        )

    def transition(
        self, task_id: UUID, status: TaskStatus, event: str, message: str
    ) -> TaskRecord:
        with connect(self.path) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT record FROM tasks WHERE id = ?", (str(task_id),)
            ).fetchone()
            if row is None:
                raise TaskNotFound(f"Task not found: {task_id}")
            task = TaskRecord.model_validate_json(
                row["record"], context={"persisted": True}
            )
            if status not in TRANSITIONS[task.status]:
                raise InvalidTransition(f"Cannot transition {task.status} to {status}")
            now = datetime.now(UTC)
            updated = task.model_copy(
                update={"status": status, "updated_at": now, "message": message}
            )
            sequence = connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM events WHERE task_id = ?",
                (str(task_id),),
            ).fetchone()[0]
            entry = TaskEvent(
                task_id=task_id,
                sequence=sequence,
                name=event,
                status=status,
                timestamp=now,
                message=message,
            )
            connection.execute(
                "UPDATE tasks SET record = ? WHERE id = ?",
                (updated.model_dump_json(), str(task_id)),
            )
            connection.execute(
                "INSERT INTO events VALUES (?, ?, ?)",
                (str(task_id), sequence, entry.model_dump_json()),
            )
        return updated

    def events(self, task_id: UUID) -> list[TaskEvent]:
        self.get(task_id)
        with connect(self.path) as connection:
            rows = connection.execute(
                "SELECT record FROM events WHERE task_id = ? ORDER BY sequence",
                (str(task_id),),
            ).fetchall()
        return [TaskEvent.model_validate_json(row["record"]) for row in rows]
