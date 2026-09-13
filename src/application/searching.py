"""Search orchestration across configured retrieval strategies."""

import logging

from repoagent.domain.errors import EmbeddingProviderError
from repoagent.domain.repository import RepositorySpec
from repoagent.ports.index_store import IndexStore
from repoagent.retrieval.embeddings import EmbeddingProvider
from repoagent.retrieval.models import (
    SearchRequest,
    SearchResponse,
    repository_identifier,
)
from repoagent.retrieval.rerank import KeywordOverlapReranker, Reranker
from repoagent.retrieval.retrievers import build_retriever


class SearchService:
    """Executes searches against persisted repository indexes.

    The CLI never touches BM25, vector stores, or providers directly;
    strategies are selected by validated request. Failing over from
    semantic retrieval to another strategy is never done silently.
    """

    def __init__(
        self,
        store: IndexStore,
        provider: EmbeddingProvider,
        reranker: Reranker | None = None,
    ) -> None:
        self._store = store
        self._provider = provider
        self._reranker = reranker

    def search(self, request: SearchRequest) -> SearchResponse:
        spec = RepositorySpec(source=request.repository)
        repo_id = repository_identifier(spec.source)
        snapshot = self._store.load(repo_id)
        self._check_provider(snapshot)
        retriever = build_retriever(
            request.strategy,
            snapshot.chunks,
            self._provider,
            snapshot.vectors,
        )
        results = retriever.search(request.query, request.top_k)
        reranked = False
        if request.rerank and results:
            reranker = self._reranker or KeywordOverlapReranker()
            results = reranker.rerank(request.query, results, request.top_k)
            reranked = True
        logging.getLogger(__name__).info(
            "Search executed", extra={"event": "search_executed"}
        )
        return SearchResponse(
            repository=spec.source,
            repository_id=repo_id,
            query=request.query,
            strategy=request.strategy,
            reranked=reranked,
            results=results,
        )

    def _check_provider(self, snapshot) -> None:
        if (
            snapshot.embedding_provider != self._provider.name
            or snapshot.embedding_dimension != self._provider.dimension
        ):
            raise EmbeddingProviderError(
                "Index was built with a different embedding provider; rebuild the index"
            )
