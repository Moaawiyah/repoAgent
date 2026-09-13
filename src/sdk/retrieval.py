"""Retrieval capability of the public SDK facade (M3)."""

from collections.abc import Sequence
from pathlib import Path

from repoagent.adapters.index_store import JsonIndexStore
from repoagent.application.indexing import IndexService
from repoagent.application.searching import SearchService
from repoagent.config import Settings
from repoagent.domain.repository import RepositorySpec
from repoagent.evaluation.evaluator import RetrievalEvaluator
from repoagent.evaluation.models import EvaluationReport, RetrievalCase
from repoagent.ports.index_store import IndexStore
from repoagent.retrieval.embeddings import (
    EmbeddingProvider,
    provider_from_settings,
)
from repoagent.retrieval.models import (
    IndexSummary,
    RetrievalStrategy,
    SearchRequest,
    SearchResponse,
)


class RetrievalApi:
    """Index, search, and evaluate repositories without CLI coupling.

    Infrastructure is injected or derived from settings; storage is a
    replaceable IndexStore and embeddings a replaceable provider.
    """

    def __init__(
        self,
        settings: Settings,
        index_store: IndexStore | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self._settings = settings
        self._index_store = index_store
        self._provider = embedding_provider

    def _services(self) -> tuple[IndexStore, EmbeddingProvider]:
        store = self._index_store or JsonIndexStore(self._settings.data_dir / "indexes")
        provider = self._provider or provider_from_settings(self._settings)
        return store, provider

    def index(self, source: str | Path, *, commit: str | None = None) -> IndexSummary:
        """Analyze, chunk, embed once, and persist a retrieval index."""
        spec = RepositorySpec(source=str(source), commit=commit)
        store, provider = self._services()
        return IndexService(store=store, provider=provider).index(spec)

    def search(
        self,
        source: str | Path,
        query: str,
        *,
        strategy: RetrievalStrategy = RetrievalStrategy.HYBRID,
        top_k: int = 5,
        rerank: bool = False,
    ) -> SearchResponse:
        """Retrieve provenance-backed code for a natural-language query."""
        request = SearchRequest(
            repository=str(source),
            query=query,
            strategy=strategy,
            top_k=top_k,
            rerank=rerank,
        )
        store, provider = self._services()
        return SearchService(store=store, provider=provider).search(request)

    def evaluate(
        self,
        source: str | Path,
        cases: list[RetrievalCase],
        *,
        k: int = 5,
        strategies: Sequence[RetrievalStrategy] | None = None,
    ) -> EvaluationReport:
        """Compare retrieval strategies on labeled cases (LLM-free)."""
        store, provider = self._services()
        service = SearchService(store=store, provider=provider)
        evaluator = RetrievalEvaluator(service, repository=str(source))
        return evaluator.evaluate(
            cases,
            k=k,
            strategies=tuple(strategies) if strategies else None,
        )
