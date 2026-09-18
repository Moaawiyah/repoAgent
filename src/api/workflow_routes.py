"""Web workflow endpoints: GitHub URL → RepairGraph / DiscoveryGraph jobs.

Requests only validate input and enqueue work; cloning, analysis, LLM calls
and sandbox execution all happen inside the background job.
"""

from typing import Literal

from fastapi import APIRouter, Query, Request

from repoagent.api.repository_routes import context
from repoagent.api.schemas import DiscoverTaskBody, FindingRepairBody, RepairTaskBody
from repoagent.api.task_results import load_result, task_graph
from repoagent.domain.audit_report import VerifiedIssue
from repoagent.domain.errors import TaskNotFound
from repoagent.domain.github import parse_github_url
from repoagent.domain.jobs import JobKind, JobRecord
from repoagent.domain.workflow import WorkflowKind, initial_stages
from repoagent.domain.workflow_results import DiscoveryWorkflowResult
from repoagent.ports.jobs import ProgressReporter


def _kind(sandboxed: bool) -> JobKind:
    return JobKind.VALIDATED_REPAIR if sandboxed else JobKind.REPAIR


def workflow_router() -> APIRouter:
    router = APIRouter()

    @router.post("/tasks/repair", status_code=202)
    def repair(body: RepairTaskBody, request: Request) -> JobRecord:
        ctx = context(request)
        repository = ctx.policy.github(body.repository_url)
        if body.sandbox_validation:
            ctx.policy.github_execution(repository)
        workflows = ctx.client.workflows(loader=ctx.loader)

        def work(progress: ProgressReporter):
            progress("Repair workflow started")
            return workflows.repair(
                repository.url,
                body.issue,
                execute=body.sandbox_validation,
                provider=ctx.provider,
                progress=progress.stage,
            )

        stages = initial_stages(WorkflowKind.REPAIR)
        kind = _kind(body.sandbox_validation)
        return ctx.jobs.submit(kind, repository.url, work, stages)

    @router.post("/tasks/discover", status_code=202)
    def discover(body: DiscoverTaskBody, request: Request) -> JobRecord:
        ctx = context(request)
        repository = ctx.policy.github(body.repository_url)
        workflows = ctx.client.workflows(loader=ctx.loader)

        def work(progress: ProgressReporter):
            progress("Discovery workflow started")
            return workflows.discover(
                repository.url,
                limit=body.limit,
                provider=ctx.provider,
                progress=progress.stage,
            )

        stages = initial_stages(WorkflowKind.DISCOVER)
        return ctx.jobs.submit(JobKind.DISCOVER, repository.url, work, stages)

    @router.post("/tasks/{job_id}/findings/{finding_id}/repair", status_code=202)
    def repair_finding(
        job_id: str, finding_id: str, body: FindingRepairBody, request: Request
    ) -> JobRecord:
        """Hand one VERIFIED finding to the same RepairGraph (same snapshot)."""
        ctx = context(request)
        result = load_result(ctx.store, job_id)
        if not isinstance(result, DiscoveryWorkflowResult):
            raise TaskNotFound("Findings exist only on discovery tasks")
        verified = VerifiedIssue.from_report(result.report, finding_id)
        handle = result.repository
        if body.sandbox_validation:
            ctx.policy.github_execution(parse_github_url(handle.source))
        workflows = ctx.client.workflows(loader=ctx.loader)

        def work(progress: ProgressReporter):
            progress(f"Repairing verified finding {finding_id}")
            return workflows.repair(
                handle.source,
                verified.to_issue(),
                execute=body.sandbox_validation,
                provider=ctx.provider,
                progress=progress.stage,
                handle=handle,
                source_finding=finding_id,
            )

        stages = initial_stages(WorkflowKind.REPAIR)
        kind = _kind(body.sandbox_validation)
        return ctx.jobs.submit(kind, handle.source, work, stages)

    @router.get("/tasks/{job_id}/graph")
    def graph(
        job_id: str,
        request: Request,
        fmt: Literal["view", "graph.json"] = Query("view", alias="format"),
    ):
        """Interactive graph view, or ``?format=graph.json`` as a download."""
        ctx = context(request)
        return task_graph(ctx.client, load_result(ctx.store, job_id), fmt)

    return router
