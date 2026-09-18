"""Discovery jobs, findings, and the discovery → RepairGraph handoff."""

from repoagent.domain.jobs import JobKind, JobRecord, JobStatus
from tests.support.api import AUTH, api_client, wait_for
from tests.support.workflows import AUDIT_URL, FixtureLoader, WorkflowProvider


def discovery(tmp_path, **extra):
    client = api_client(
        tmp_path, provider=WorkflowProvider(), loader=FixtureLoader(), **extra
    )
    job = client.post("/api/tasks/discover", json={"repository_url": AUDIT_URL})
    assert job.status_code == 202 and job.json()["kind"] == "discover"
    record = wait_for(client, job.json()["id"])
    assert record["status"] == "succeeded"
    return client, record, client.get(f"/api/tasks/{record['id']}/result").json()


def test_discovery_job_returns_classified_findings_and_graph(tmp_path):
    client, record, body = discovery(tmp_path)
    assert all(s["status"] == "done" for s in record["stages"])
    report = body["result"]["report"]
    counts = report["metrics"]
    assert counts["verified"] and counts["uncertain"] and counts["rejected"]
    finding = report["candidates"][0]
    assert {"file", "start_line", "severity", "verification", "evidence"} <= set(
        finding
    )
    assert report["repair"] is None  # discovery never repairs by itself
    graph = client.get(f"/api/tasks/{record['id']}/graph").json()
    assert graph["repository"] == "acme/audit_repo" and graph["nodes"]


def test_verified_finding_hands_off_to_repair_graph(tmp_path):
    client, record, body = discovery(tmp_path)
    candidates = body["result"]["report"]["candidates"]
    verified = next(c for c in candidates if c["status"] == "verified")
    rejected = next(c for c in candidates if c["status"] == "rejected")
    base = f"/api/tasks/{record['id']}/findings"
    refused = client.post(f"{base}/{rejected['id']}/repair", json={})
    assert refused.status_code == 409
    assert client.post(f"{base}/{'0' * 16}/repair", json={}).status_code == 409
    sandboxed = client.post(
        f"{base}/{verified['id']}/repair", json={"sandbox_validation": True}
    )
    assert sandboxed.status_code == 403
    job = client.post(f"{base}/{verified['id']}/repair", json={})
    assert job.status_code == 202 and job.json()["kind"] == "repair"
    done = wait_for(client, job.json()["id"])
    assert done["status"] == "succeeded"
    repair = client.get(f"/api/tasks/{done['id']}/result").json()["result"]
    assert repair["workflow"] == "repair" and repair["source_finding"] == verified["id"]
    assert verified["file"] in repair["issue"]["description"]
    assert repair["repository"] == body["result"]["repository"]
    assert repair["sandbox_validation"] is False


def test_graph_and_handoff_require_a_finished_workflow_task(tmp_path):
    client = api_client(tmp_path, provider=WorkflowProvider(), loader=FixtureLoader())
    assert client.get(f"/api/tasks/{'f' * 32}/graph").status_code == 404
    assert client.get("/api/tasks/not-an-id/graph").status_code == 404
    store = client.app.state.context.store
    running = JobRecord(kind=JobKind.DISCOVER, repository=AUDIT_URL)
    store.save(running.transition(JobStatus.RUNNING, "busy"))
    assert client.get(f"/api/tasks/{running.id}/graph").status_code == 409
    failed = JobRecord(kind=JobKind.DISCOVER, repository=AUDIT_URL)
    store.save(failed.transition(JobStatus.FAILED, "boom"))
    assert client.get(f"/api/tasks/{failed.id}/graph").status_code == 409
    legacy = client.post(
        "/api/investigate", json={"repository": str(AUTH), "issue": "Login fails"}
    )
    assert wait_for(client, legacy.json()["id"])["status"] == "succeeded"
    assert client.get(f"/api/tasks/{legacy.json()['id']}/graph").status_code == 404
