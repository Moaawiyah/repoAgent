"""Small public SDK mixin exposing web workflows and LangChain retrieval."""

from pathlib import Path
from typing import Protocol

from repoagent.application.searching import SearchService
from repoagent.config import Settings
from repoagent.ports.sandbox import SandboxRunner
from repoagent.retrieval.langchain_adapters import RepoAgentRetriever
from repoagent.retrieval.models import RetrievalStrategy
from repoagent.sdk.retrieval import RetrievalApi
from repoagent.sdk.workflows import Loader, WorkflowApi


class WorkflowClient(Protocol):
    _settings: Settings | None
    _sandbox_runner: SandboxRunner | None

    def retrieval(self) -> RetrievalApi: ...


class WorkflowCapability:
    def workflows(self: WorkflowClient, *, loader: Loader | None = None) -> WorkflowApi:
        """RepairGraph / DiscoveryGraph over local paths or GitHub URLs."""
        return WorkflowApi(self, self._settings or Settings(), loader)

    def langchain_retriever(
        self: WorkflowClient,
        source: str | Path,
        *,
        top_k: int = 5,
        strategy: RetrievalStrategy = RetrievalStrategy.HYBRID_GRAPH,
    ) -> RepoAgentRetriever:
        """The existing hybrid/graph retrieval as a LangChain retriever."""
        store, embedding = self.retrieval()._services()
        return RepoAgentRetriever(
            search_service=SearchService(store, embedding),
            repository=str(source),
            strategy=strategy,
            top_k=top_k,
        )
