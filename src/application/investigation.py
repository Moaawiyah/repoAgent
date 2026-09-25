"""Investigation orchestration: request validation and agent execution."""

import logging
from pathlib import Path
from uuid import uuid4

from pydantic import Field, field_validator

from repoagent.agent.investigator import InvestigatorAgent
from repoagent.ai.provider import LLMProvider, require_provider
from repoagent.analysis.models import AnalysisModel
from repoagent.application.searching import SearchService
from repoagent.domain.investigation import (
    InvestigationLimits,
    InvestigationReport,
    Issue,
)
from repoagent.graph.policy import GraphPolicy
from repoagent.graph.store import store_from_snapshot
from repoagent.ports.index_store import IndexStore
from repoagent.retrieval.embeddings import EmbeddingProvider
from repoagent.retrieval.models import RetrievalStrategy
from repoagent.tools.repository import RepositoryToolkit


class InvestigateRequest(AnalysisModel):
    """Validated investigation input."""

    repository: str
    issue: Issue
    max_iterations: int | None = Field(default=None, ge=1, le=10)
    top_k: int = Field(default=5, ge=1, le=10)
    use_graph: bool = True

    @field_validator("issue", mode="before")
    @classmethod
    def _coerce_issue(cls, value) -> Issue:
        if isinstance(value, str):
            return Issue(description=value)
        return value


class InvestigationService:
    """Runs the read-only investigator against an indexed repository."""

    def __init__(
        self,
        store: IndexStore,
        embedding_provider: EmbeddingProvider,
        llm_provider: LLMProvider | None,
        graph_policy: GraphPolicy | None = None,
    ) -> None:
        self._store = store
        self._embedding = embedding_provider
        self._llm = llm_provider
        self._policy = graph_policy

    def investigate(
        self, request: InvestigateRequest, limits: InvestigationLimits | None = None
    ) -> InvestigationReport:
        """Investigate the issue; never modifies the target repository."""
        provider = require_provider(self._llm, "investigations")
        search = SearchService(self._store, self._embedding, graph_policy=self._policy)
        graph = None
        snapshot = search.snapshot(request.repository)
        if request.use_graph and snapshot.graph is not None and snapshot.graph.nodes:
            graph = store_from_snapshot(snapshot.graph)
        strategy = RetrievalStrategy.HYBRID_GRAPH if graph else RetrievalStrategy.HYBRID
        bounded = limits or InvestigationLimits()
        if request.max_iterations is not None:
            bounded = InvestigationLimits.model_validate(
                {
                    **bounded.model_dump(),
                    "max_iterations": request.max_iterations,
                }
            )
        toolkit = RepositoryToolkit(
            request.repository,
            search,
            graph,
            Path(snapshot.repository_root),
            top_k=request.top_k,
            strategy=strategy,
            chunks=snapshot.chunks,
            max_calls=bounded.max_tool_calls,
        )
        task_id = uuid4().hex
        logging.getLogger(__name__).info(
            "Investigation started",
            extra={"event": "investigation_started", "task_id": task_id},
        )
        agent = InvestigatorAgent(toolkit, provider, bounded)
        return agent.run(request.repository, task_id, request.issue)
