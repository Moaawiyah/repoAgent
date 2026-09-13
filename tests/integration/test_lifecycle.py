"""Terminal-state and concurrent writer consistency."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from repoagent.adapters.sqlite.task_store import SQLiteTaskStore
from repoagent.domain.errors import InvalidTransition
from repoagent.domain.tasks import TaskRequest, TaskStatus


@pytest.mark.parametrize("terminal", [TaskStatus.BLOCKED, TaskStatus.FAILED])
def test_pending_terminal_states_cannot_resume(tmp_path, terminal):
    store = SQLiteTaskStore(tmp_path / "tasks.sqlite3")
    task = store.create(TaskRequest(kind="benchmark", suite="synthetic"))
    with pytest.raises(InvalidTransition):
        store.transition(task.id, TaskStatus.SUCCEEDED, "completed", "Not started")
    store.transition(task.id, terminal, "stopped", "Stopped")
    with pytest.raises(InvalidTransition):
        store.transition(task.id, TaskStatus.RUNNING, "resumed", "Not permitted")
    assert len(store.events(task.id)) == 2


def test_competing_transitions_are_serialized(tmp_path):
    store = SQLiteTaskStore(tmp_path / "tasks.sqlite3")
    task = store.create(TaskRequest(kind="benchmark", suite="synthetic"))

    def transition(status):
        try:
            return store.transition(task.id, status, "stopped", "Stopped").status
        except InvalidTransition:
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(
            executor.map(transition, [TaskStatus.BLOCKED, TaskStatus.FAILED])
        )
    assert outcomes.count(None) == 1
    assert store.get(task.id).status in {TaskStatus.BLOCKED, TaskStatus.FAILED}
    assert [event.sequence for event in store.events(task.id)] == [1, 2]
