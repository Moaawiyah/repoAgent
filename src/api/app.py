"""FastAPI application factory; adapters are wired here, not in routes."""

from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from repoagent.adapters.job_queue import LocalJobQueue
from repoagent.adapters.job_store import FileJobStore
from repoagent.ai.openai_provider import llm_provider_from_settings
from repoagent.api.context import ApiContext
from repoagent.api.job_routes import job_router
from repoagent.api.policy import ApiConflict, ApiForbidden, ApiPolicy, ApiUnauthorized
from repoagent.api.repository_routes import repository_router
from repoagent.api.workflow_routes import workflow_router
from repoagent.config import Settings
from repoagent.domain.errors import (
    AuditError,
    IndexNotFound,
    LLMError,
    RepoAgentError,
    RepositoryInvalid,
    StorageError,
    TaskNotFound,
)
from repoagent.sdk import RepoAgent

STATUS = (
    (ApiUnauthorized, 401),
    (ApiForbidden, 403),
    (ApiConflict, 409),
    (AuditError, 409),
    (TaskNotFound, 404),
    (IndexNotFound, 404),
    (RepositoryInvalid, 400),
    (LLMError, 503),
    (StorageError, 500),
)


def _error(_: Request, error: Exception) -> JSONResponse:
    code = next((status for kind, status in STATUS if isinstance(error, kind)), 400)
    detail = "Storage operation failed" if code == 500 else str(error)[:500]
    return JSONResponse(status_code=code, content={"detail": detail})


def create_app(
    settings: Settings | None = None,
    *,
    client: RepoAgent | None = None,
    context: ApiContext | None = None,
    dashboard: Path | None = None,
) -> FastAPI:
    settings = settings or Settings()
    if context is None:
        store = FileJobStore(settings.data_dir / "jobs")
        context = ApiContext(
            client=client or RepoAgent(settings=settings),
            policy=ApiPolicy(settings),
            jobs=LocalJobQueue(
                store, settings.api_max_workers, settings.workflow_task_timeout
            ),
            store=store,
            provider=llm_provider_from_settings(settings),
        )

    def authorize(request: Request) -> None:
        context.policy.authorize(request.headers.get("authorization"))

    app = FastAPI(title="RepoAgent API", version="0.1.0")
    app.state.context = context
    app.add_exception_handler(RepoAgentError, _error)
    guarded = [Depends(authorize)]
    app.include_router(repository_router(), prefix="/api", dependencies=guarded)
    app.include_router(workflow_router(), prefix="/api", dependencies=guarded)
    app.include_router(job_router(), prefix="/api", dependencies=guarded)
    if dashboard is not None and (dashboard / "index.html").is_file():
        app.mount("/", StaticFiles(directory=dashboard, html=True), name="dashboard")
    return app
