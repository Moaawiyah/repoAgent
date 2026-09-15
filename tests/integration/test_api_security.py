"""Token authentication, unfinished jobs, worker failures, and serve safety."""

from typer.testing import CliRunner

from repoagent.adapters.job_queue import LocalJobQueue
from repoagent.adapters.job_store import FileJobStore
from repoagent.cli.main import app
from repoagent.domain.errors import IndexNotFound
from repoagent.domain.jobs import JobKind, JobRecord, JobStatus
from tests.support.api import AUTH, api_client


def test_bearer_token_is_required_when_configured(tmp_path):
    client = api_client(tmp_path, token="s3cret")
    assert client.get("/api/health").status_code == 401
    wrong = {"Authorization": "Bearer nope"}
    assert client.get("/api/health", headers=wrong).status_code == 401
    good = {"Authorization": "Bearer s3cret"}
    assert client.get("/api/health", headers=good).status_code == 200


class HoldQueue:
    """Accepts jobs without running them (simulates a busy worker)."""

    def __init__(self, store):
        self.store = store

    def submit(self, kind, repository, work):
        record = JobRecord(kind=kind, repository=repository)
        self.store.save(record)
        return record


def test_result_of_unfinished_job_is_conflict(tmp_path):
    store = FileJobStore(tmp_path / "jobs")
    client = api_client(tmp_path, queue=HoldQueue(store))
    job = client.post("/api/investigate", json={"repository": str(AUTH), "issue": "x"})
    assert client.get(f"/api/tasks/{job.json()['id']}/result").status_code == 409


def test_worker_failures_are_recorded_not_raised(tmp_path):
    store = FileJobStore(tmp_path / "jobs")
    queue = LocalJobQueue(store)

    def domain_failure(progress):
        raise IndexNotFound("No index for repository")

    def crash(progress):
        raise RuntimeError("secret internal detail")

    first = queue.submit(JobKind.INVESTIGATE, "repo", domain_failure)
    second = queue.submit(JobKind.INVESTIGATE, "repo", crash)
    queue.shutdown()
    assert store.get(first.id).error == "No index for repository"
    failed = store.get(second.id)
    assert failed.status == JobStatus.FAILED and failed.error == "Internal error"
    assert "secret" not in failed.model_dump_json()
    assert FileJobStore(tmp_path / "none").recent(5) == []


def test_serve_refuses_public_host_without_token(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("uvicorn.run", lambda *args, **kwargs: calls.append(kwargs))
    runner = CliRunner()
    base = ["--data-dir", str(tmp_path / "data"), "serve"]
    public = runner.invoke(app, [*base, "--host", "0.0.0.0"])
    assert public.exit_code == 2 and "API_TOKEN" in public.output and not calls
    local = runner.invoke(app, [*base, "--allow-root", str(AUTH), "--port", "9001"])
    assert local.exit_code == 0 and calls[0]["port"] == 9001
