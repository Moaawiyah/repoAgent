"""Web workflow API: GitHub URL validation, repair/discover jobs, stages."""

import pytest

from tests.support.api import api_client, wait_for
from tests.support.workflows import (
    AUDIT_URL,
    AUTH_URL,
    FixtureLoader,
    WorkflowProvider,
)

ISSUE = "Users with uppercase email addresses cannot log in"


@pytest.fixture
def loader():
    return FixtureLoader()


@pytest.fixture
def client(tmp_path, loader):
    return api_client(
        tmp_path,
        provider=WorkflowProvider(),
        loader=loader,
        api_execution_github=["acme/auth_bug"],
    )


def result_of(client, job_id):
    return client.get(f"/api/tasks/{job_id}/result").json()


def test_config_describes_web_capabilities(client):
    config = client.get("/api/config").json()
    assert config["github_enabled"] and config["llm_configured"]
    assert config["github_execution"] == ["acme/auth_bug"]


@pytest.mark.parametrize(
    "url",
    ["", "https://gitlab.com/o/r", "https://github.com/o", "/etc/passwd",
     "https://github.com/o/r?x=1", "git@github.com:o/r.git"],
)  # fmt: skip
def test_invalid_repository_urls_never_create_jobs(client, loader, url):
    for path, body in (
        ("/api/tasks/repair", {"repository_url": url, "issue": ISSUE}),
        ("/api/tasks/discover", {"repository_url": url}),
    ):
        response = client.post(path, json=body)
        assert response.status_code in (400, 422) and "detail" in response.json()
    assert loader.calls == [] and client.get("/api/tasks").json() == []


def test_request_bodies_are_strict(client):
    short = {"repository_url": AUTH_URL, "issue": "bug"}
    assert client.post("/api/tasks/repair", json=short).status_code == 422
    extra = {"repository_url": AUTH_URL, "command": "rm -rf /"}
    assert client.post("/api/tasks/discover", json=extra).status_code == 422


def test_sandbox_validation_requires_an_allowlisted_repository(client, loader):
    body = {"repository_url": AUDIT_URL, "issue": ISSUE, "sandbox_validation": True}
    response = client.post("/api/tasks/repair", json=body)
    assert (
        response.status_code == 403 and "server operator" in response.json()["detail"]
    )
    assert loader.calls == []


def test_github_can_be_disabled(tmp_path):
    client = api_client(tmp_path, api_allow_github=False, loader=FixtureLoader())
    body = {"repository_url": AUTH_URL}
    assert client.post("/api/tasks/discover", json=body).status_code == 403


def test_repair_job_reports_stages_result_and_graph(client):
    body = {"repository_url": AUTH_URL, "issue": ISSUE, "sandbox_validation": True}
    job = client.post("/api/tasks/repair", json=body)
    assert job.status_code == 202
    queued = job.json()
    assert queued["kind"] == "validated_repair" and queued["repository"] == AUTH_URL
    assert [s["status"] for s in queued["stages"]] == ["pending"] * 11
    record = wait_for(client, queued["id"])
    assert record["status"] == "succeeded"
    stages = {s["key"]: s for s in record["stages"]}
    assert stages["docker_validation"]["status"] == "done"
    assert stages["developer"]["visits"] >= 1 and stages["report"]["status"] == "done"
    result = result_of(client, queued["id"])["result"]
    assert result["workflow"] == "repair" and result["report"]["status"] == "validated"
    assert result["repository"]["commit"] == "a" * 40
    graph = client.get(f"/api/tasks/{queued['id']}/graph").json()
    kinds = {n["kind"] for n in graph["nodes"]}
    assert {"module", "class", "method"} <= kinds and graph["edges"]
    assert any(n["focus"] for n in graph["nodes"])
    assert "chunk_id" not in graph["nodes"][0]
    download = client.get(f"/api/tasks/{queued['id']}/graph?format=graph.json")
    assert "graph.json" in download.headers["content-disposition"]
    assert download.json()["schema_version"] == "1.0"
