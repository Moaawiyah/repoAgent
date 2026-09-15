"""Long-running operations run as background jobs; HTTP never blocks on them."""

import json

from fastapi import APIRouter, Request, Response

from repoagent.api.repository_routes import context
from repoagent.api.schemas import InvestigateBody, RepairBody
from repoagent.domain.jobs import JobKind, JobRecord

MAX_JOBS_LISTED = 50


def job_router() -> APIRouter:
    router = APIRouter()

    @router.post("/investigate", status_code=202)
    def investigate(body: InvestigateBody, request: Request) -> JobRecord:
        ctx = context(request)
        path = ctx.policy.repository(body.repository)

        def work(progress):
            progress("Repository analysis and indexing")
            ctx.client.index(path)
            progress("Investigator running")
            return ctx.client.investigate(
                path,
                body.issue,
                max_iterations=body.max_iterations,
                top_k=body.top_k,
                provider=ctx.provider,
            )

        return ctx.jobs.submit(JobKind.INVESTIGATE, str(path), work)

    @router.post("/repair", status_code=202)
    def repair(body: RepairBody, request: Request) -> JobRecord:
        ctx = context(request)
        if body.execute:
            path = ctx.policy.execution(body.repository)
        else:
            path = ctx.policy.repository(body.repository)

        def work(progress):
            progress("Repository analysis and indexing")
            ctx.client.index(path)
            if not body.execute:
                progress("Investigator, Developer and Reviewer (static)")
                return ctx.client.repair(
                    path, body.issue, max_revisions=body.max_revisions,
                    provider=ctx.provider,
                )  # fmt: skip
            progress("Investigation, repair loop and Docker validation")
            return ctx.client.repair_and_validate(
                path, body.issue, max_attempts=body.max_attempts,
                max_revisions=body.max_revisions, timeout=body.timeout,
                provider=ctx.provider,
            )  # fmt: skip

        kind = JobKind.VALIDATED_REPAIR if body.execute else JobKind.REPAIR
        return ctx.jobs.submit(kind, str(path), work)

    @router.get("/tasks")
    def tasks(request: Request) -> list[JobRecord]:
        return context(request).store.recent(MAX_JOBS_LISTED)

    @router.get("/tasks/{job_id}")
    def task(job_id: str, request: Request) -> JobRecord:
        return context(request).store.get(job_id)

    @router.get("/tasks/{job_id}/result")
    def result(job_id: str, request: Request) -> Response:
        store = context(request).store
        record = store.get(job_id)
        if not record.status.terminal:
            return Response(status_code=409, content='{"detail":"Job not finished"}')
        payload = store.result(job_id) if record.status == "succeeded" else "null"
        body = {"job": record.model_dump(mode="json"), "result": json.loads(payload)}
        return Response(content=json.dumps(body), media_type="application/json")

    @router.get("/benchmarks/runs")
    def benchmark_runs(request: Request) -> list[str]:
        return context(request).client.benchmarks().runs()

    @router.get("/benchmarks/runs/{run_id}")
    def benchmark_run(run_id: str, request: Request):
        return context(request).client.benchmarks().load(run_id)

    return router
