"""API endpoints delegate to the SDK and enforce the security policy."""

import pytest

from tests.support.api import AUTH, FIXTURES, api_client, wait_for

ISSUE = "Users with uppercase email addresses cannot log in"


@pytest.fixture
def client(tmp_path):
    return api_client(tmp_path)


def test_health_config_analyze_index_search_graph(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/config").json()["execution_repositories"] == [str(AUTH)]
    analysis = client.post("/api/analyze", json={"repository": str(AUTH)}).json()
    assert analysis["python_files"] > 0
    assert client.post("/api/index", json={"repository": str(AUTH)}).status_code == 200
    search = client.post(
        "/api/search", json={"repository": str(AUTH), "query": "email lookup"}
    )
    assert search.status_code == 200 and search.json()["results"]
    summary = client.get("/api/graph", params={"repository": str(AUTH)}).json()
    assert summary["node_count"] > 0
    symbol = "app.users.repository.UserRepository.find_by_email"
    inspection = client.get(
        "/api/graph", params={"repository": str(AUTH), "symbol": symbol}
    ).json()
    assert inspection["node"]["node_id"] == symbol
    missing = client.get("/api/graph", params={"repository": str(AUTH), "symbol": "x"})
    assert missing.status_code == 400


@pytest.mark.parametrize(
    "repository, status",
    [
        ("/etc", 403),
        (str(FIXTURES / ".." / ".."), 403),
        ("https://github.com/o/r", 403),
        ("git@github.com:o/r.git", 403),
        (str(FIXTURES / "does-not-exist"), 403),
    ],
)
def test_repository_allowlist(client, repository, status):
    response = client.post("/api/analyze", json={"repository": repository})
    assert response.status_code == status and "detail" in response.json()


def test_invalid_bodies_are_rejected(client):
    assert client.post("/api/analyze", json={}).status_code == 422
    body = {"repository": str(AUTH), "command": "rm -rf /"}
    assert client.post("/api/analyze", json=body).status_code == 422
    body = {"repository": str(AUTH), "issue": ISSUE, "max_attempts": 99}
    assert client.post("/api/repair", json=body).status_code == 422


def test_investigation_job_lifecycle(client):
    job = client.post(
        "/api/investigate", json={"repository": str(AUTH), "issue": ISSUE}
    )
    assert job.status_code == 202 and job.json()["status"] == "queued"
    record = wait_for(client, job.json()["id"])
    assert record["status"] == "succeeded"
    messages = [event["message"] for event in record["events"]]
    assert "Investigator running" in messages
    result = client.get(f"/api/tasks/{record['id']}/result").json()
    assert result["result"]["termination_reason"] == "confident_root_cause"
    assert [t["id"] for t in client.get("/api/tasks").json()] == [record["id"]]


def test_static_and_executed_repair_jobs(client):
    static = client.post("/api/repair", json={"repository": str(AUTH), "issue": ISSUE})
    record = wait_for(client, static.json()["id"])
    result = client.get(f"/api/tasks/{record['id']}/result").json()["result"]
    assert result["status"] == "approved_for_runtime_validation"
    body = {"repository": str(AUTH), "issue": ISSUE, "execute": True}
    executed = client.post("/api/repair", json=body)
    assert executed.json()["kind"] == "validated_repair"
    record = wait_for(client, executed.json()["id"])
    result = client.get(f"/api/tasks/{record['id']}/result").json()["result"]
    assert result["status"] == "validated" and result["attempts"]


def test_execution_is_limited_to_allowlisted_repositories(client):
    body = {
        "repository": str(FIXTURES / "bench_cache"),
        "issue": ISSUE,
        "execute": True,
    }
    response = client.post("/api/repair", json=body)
    assert (
        response.status_code == 403 and "demo repositories" in response.json()["detail"]
    )
    assert client.get("/api/tasks").json() == []


def test_unknown_tasks_and_benchmark_runs(client):
    assert client.get("/api/tasks/" + "0" * 32).status_code == 404
    assert client.get("/api/tasks/../../etc").status_code == 404
    assert client.get("/api/benchmarks/runs").json() == []
    assert client.get("/api/benchmarks/runs/../x").status_code == 404
