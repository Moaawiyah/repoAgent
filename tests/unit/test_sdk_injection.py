"""The SDK composes the TaskStore contract without depending on SQLite behavior."""

from repoagent import RepoAgent, TaskEvent, TaskRecord, TaskRequest, TaskStatus


class RecordingStore:
    """Minimal test double capturing SDK/service calls."""

    def __init__(self):
        self.records = {}
        self.transitions = []

    def create(self, request):
        record = TaskRecord(request=request)
        self.records[record.id] = record
        return record

    def get(self, task_id):
        return self.records[task_id]

    def transition(self, task_id, status, event, message):
        record = self.records[task_id].model_copy(
            update={"status": status, "message": message}
        )
        self.records[task_id] = record
        self.transitions.append((task_id, status, event, message))
        return record

    def events(self, task_id):
        return [
            TaskEvent(
                task_id=task_id,
                sequence=1,
                name=event,
                status=status,
                timestamp=self.records[task_id].updated_at,
                message=message,
            )
            for identifier, status, event, message in self.transitions
            if identifier == task_id
        ]


def test_injected_store_bypasses_environment_and_default_adapter(monkeypatch):
    from repoagent.sdk import tasks as module

    def forbidden(*args, **kwargs):
        raise AssertionError("Injected storage must not initialize SQLite")

    monkeypatch.setattr(module, "SQLiteTaskStore", forbidden)
    monkeypatch.setenv("REPOAGENT_MAX_RETRIES", "invalid")
    store = RecordingStore()
    client = RepoAgent(store=store)
    request = TaskRequest(kind="benchmark", suite="synthetic")
    task = client.submit(request)
    assert task.status is TaskStatus.BLOCKED
    assert store.get(task.id).request == request
    assert client.get_task(task.id) == task
    assert client.task_events(task.id)[0].name == "capability_unavailable"
    assert len(store.transitions) == 1
