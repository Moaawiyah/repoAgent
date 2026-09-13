"""Durability, lifecycle constraints, schema handling and atomic transactions."""

import sqlite3
from uuid import uuid4

import pytest

from repoagent.adapters.sqlite.database import connect
from repoagent.adapters.sqlite.task_store import SQLiteTaskStore
from repoagent.domain.errors import InvalidTransition, TaskNotFound, UnsupportedSchema
from repoagent.domain.repository import RepositorySpec
from repoagent.domain.tasks import TaskRequest, TaskStatus


@pytest.fixture
def store(tmp_path):
    return SQLiteTaskStore(tmp_path / "data" / "tasks.sqlite3")


@pytest.fixture
def request_model():
    return TaskRequest(kind="benchmark", suite="synthetic")


def test_roundtrip_and_ordered_events(store, request_model):
    task = store.create(request_model)
    store.transition(task.id, TaskStatus.RUNNING, "started", "Task started")
    completed = store.transition(task.id, TaskStatus.SUCCEEDED, "completed", "Done")
    reopened = SQLiteTaskStore(store.path)
    assert reopened.get(task.id) == completed
    events = reopened.events(task.id)
    assert [event.sequence for event in events] == [1, 2, 3]
    assert [event.status for event in events] == ["pending", "running", "succeeded"]
    assert completed.updated_at >= completed.created_at
    with pytest.raises(InvalidTransition):
        store.transition(task.id, TaskStatus.RUNNING, "started", "Again")
    assert len(store.events(task.id)) == 3


def test_missing_tasks(store):
    missing = uuid4()
    for operation in (
        lambda: store.get(missing),
        lambda: store.events(missing),
        lambda: store.transition(missing, TaskStatus.FAILED, "failed", "Missing"),
    ):
        with pytest.raises(TaskNotFound):
            operation()


def test_transition_rolls_back_when_event_write_fails(store, request_model):
    task = store.create(request_model)
    with connect(store.path) as connection:
        connection.execute(
            "CREATE TRIGGER reject_event BEFORE INSERT ON events "
            "BEGIN SELECT RAISE(ABORT, 'forced failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError):
        store.transition(task.id, TaskStatus.BLOCKED, "blocked", "Unavailable")
    assert store.get(task.id) == task
    assert len(store.events(task.id)) == 1


def test_create_rolls_back_when_event_write_fails(store, request_model):
    with connect(store.path) as connection:
        connection.execute(
            "CREATE TRIGGER reject_event BEFORE INSERT ON events "
            "BEGIN SELECT RAISE(ABORT, 'forced failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError):
        store.create(request_model)
    with connect(store.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 0
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


@pytest.mark.parametrize("version", [2, 999])
def test_unsupported_schema(tmp_path, version):
    path = tmp_path / "tasks.sqlite3"
    with connect(path) as connection:
        connection.execute(f"PRAGMA user_version = {version}")
    with pytest.raises(UnsupportedSchema):
        SQLiteTaskStore(path)
    with connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == version


def test_nonempty_unversioned_database(tmp_path):
    path = tmp_path / "existing.sqlite3"
    with connect(path) as connection:
        connection.execute("CREATE TABLE unrelated (value TEXT)")
    with pytest.raises(UnsupportedSchema):
        SQLiteTaskStore(path)


def test_historical_task_survives_deleted_source(store, tmp_path):
    source = tmp_path / "target"
    source.mkdir()
    task = store.create(
        TaskRequest(kind="index", repository=RepositorySpec(source=str(source)))
    )
    source.rmdir()
    assert store.get(task.id).request.repository.source == str(source)
