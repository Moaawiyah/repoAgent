"""API test wiring: real SDK and job store with fake sandbox/provider."""

import time
from pathlib import Path

from fastapi.testclient import TestClient

from repoagent import RepoAgent, Settings
from repoagent.adapters.job_queue import LocalJobQueue
from repoagent.adapters.job_store import FileJobStore
from repoagent.api.app import create_app
from repoagent.api.context import ApiContext
from repoagent.api.policy import ApiPolicy
from tests.support.execution_provider import ExecutionProvider
from tests.support.sandbox import FakeSandboxRunner, execution, pytest_result

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
AUTH = FIXTURES / "auth_bug"


def api_client(
    tmp_path, token=None, queue=None, runner=None, provider=None, loader=None, **extra
) -> TestClient:
    settings = Settings(
        data_dir=tmp_path / "data",
        api_allowed_roots=[FIXTURES],
        api_execution_repositories=[AUTH],
        api_token=token,
        **extra,
    )
    sandbox = runner or FakeSandboxRunner(attempts=[execution(pytest_result(passed=3))])
    store = FileJobStore(tmp_path / "jobs")
    context = ApiContext(
        client=RepoAgent(settings=settings, sandbox_runner=sandbox),
        policy=ApiPolicy(settings),
        jobs=queue or LocalJobQueue(store),
        store=store,
        provider=provider or ExecutionProvider(),
        loader=loader,
    )
    return TestClient(create_app(settings, context=context))


def wait_for(client: TestClient, job_id: str, headers=None) -> dict:
    for _ in range(200):
        record = client.get(f"/api/tasks/{job_id}", headers=headers).json()
        if record["status"] in ("succeeded", "failed"):
            return record
        time.sleep(0.02)
    raise AssertionError("Job did not finish")
