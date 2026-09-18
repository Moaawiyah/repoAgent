"""Read stored workflow results and derive the task graph for the web UI."""

import json

from fastapi.responses import Response

from repoagent.api.policy import ApiConflict
from repoagent.domain.errors import TaskNotFound
from repoagent.domain.jobs import JobStatus
from repoagent.domain.workflow_results import (
    DiscoveryWorkflowResult,
    RepairWorkflowResult,
)
from repoagent.graph.builder import RepositoryGraphBuilder
from repoagent.graph.serializer import build_document
from repoagent.graph.view import GraphView, build_view
from repoagent.ports.jobs import JobStore
from repoagent.sdk import RepoAgent

WorkflowResult = RepairWorkflowResult | DiscoveryWorkflowResult


def load_result(store: JobStore, job_id: str) -> WorkflowResult:
    record = store.get(job_id)
    if not record.status.terminal:
        raise ApiConflict("Task is still running")
    if record.status != JobStatus.SUCCEEDED:
        raise ApiConflict("Task failed and has no result")
    data = json.loads(store.result(job_id))
    workflow = data.get("workflow") if isinstance(data, dict) else None
    if workflow == "repair":
        return RepairWorkflowResult.model_validate(data)
    if workflow == "discover":
        return DiscoveryWorkflowResult.model_validate(data)
    raise TaskNotFound("This task has no repository workflow result")


def focus_of(result: WorkflowResult) -> set[str]:
    """Symbols and files the result refers to, highlighted in the graph."""
    if isinstance(result, DiscoveryWorkflowResult):
        found = result.report.candidates
        return {c.file for c in found} | {c.symbol for c in found if c.symbol}
    investigation = result.report.investigation
    if investigation is None:
        return set()
    return set(investigation.relevant_files) | set(investigation.relevant_symbols)


def task_graph(
    client: RepoAgent, result: WorkflowResult, fmt: str
) -> GraphView | Response:
    """Rebuild the native graph from the task's isolated workspace snapshot."""
    analysis = client.analyze(result.repository.path)
    snapshot = RepositoryGraphBuilder().build(analysis).to_snapshot()
    if fmt == "graph.json":
        document = build_document(
            snapshot,
            repository=result.repository.name,
            files=analysis.python_files,
            symbols=len(analysis.symbols),
        )
        body = json.dumps(document.model_dump(mode="json"), indent=2, sort_keys=True)
        return Response(
            content=body,
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="graph.json"'},
        )
    return build_view(snapshot, result.repository.name, focus_of(result))
