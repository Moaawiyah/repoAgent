"""Synchronous, read-only endpoints: analysis, indexing, search, graph."""

from fastapi import APIRouter, Request

from repoagent import __version__
from repoagent.api.context import ApiContext
from repoagent.api.schemas import RepositoryBody, SearchBody
from repoagent.graph.inspection import graph_inspection, graph_summary
from repoagent.graph.store import store_from_snapshot


def context(request: Request) -> ApiContext:
    return request.app.state.context


def repository_router() -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    @router.get("/config")
    def config(request: Request) -> dict:
        ctx = context(request)
        return {
            "execution_repositories": ctx.policy.execution_repositories,
            "llm_configured": ctx.provider is not None,
            **ctx.policy.public_config(),
        }

    @router.post("/analyze")
    def analyze(body: RepositoryBody, request: Request):
        ctx = context(request)
        return ctx.client.analyze(ctx.policy.repository(body.repository))

    @router.post("/index")
    def index(body: RepositoryBody, request: Request):
        ctx = context(request)
        return ctx.client.index(ctx.policy.repository(body.repository))

    @router.post("/search")
    def search(body: SearchBody, request: Request):
        ctx = context(request)
        path = ctx.policy.repository(body.repository)
        return ctx.client.search(
            path, body.query, strategy=body.strategy, top_k=body.top_k
        )

    @router.get("/graph")
    def graph(repository: str, request: Request, symbol: str | None = None):
        """Reuses the M4 graph; neighborhoods only, never a new graph system."""
        ctx = context(request)
        path = ctx.policy.repository(repository)
        snapshot = ctx.client.retrieval().graph(path)
        if symbol:
            return graph_inspection(store_from_snapshot(snapshot), snapshot, symbol)
        return graph_summary(snapshot, path.name)

    return router
