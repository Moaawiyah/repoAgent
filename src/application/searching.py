"""Search orchestration across configured retrieval strategies."""

import logging

from repoagent.domain.errors import EmbeddingProviderError
from repoagent.domain.repository import RepositorySpec
from repoagent.graph.expansion import GraphExpander
from repoagent.graph.store import store_from_snapshot
from repoagent.ports.index_store import IndexStore
from repoagent.retrieval.embeddings import EmbeddingProvider
from repoagent.retrieval.models import (
    RetrievalStrategy,
    SearchRequest,
    SearchResponse,
    repository_identifier,
)
from repoagent.retrieval.persistence import IndexSnapshot
from repoagent.retrieval.rerank import KeywordOverlapReranker, Reranker
from repoagent.retrieval.retrievers import Retriever, build_retriever


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
        self._retrievers: dict[tuple[str, str], Retriever] = {}
        self._snapshots: dict[str, IndexSnapshot] = {}

    def snapshot(self, repository: str) -> IndexSnapshot:
        """Return the loaded (cached) index snapshot for a repository."""
        repo_id = repository_identifier(RepositorySpec(source=repository).source)
        if repo_id not in self._snapshots:
            self._snapshots[repo_id] = self._load(repository)
        return self._snapshots[repo_id]

    def retriever(
        self, repository: str, strategy: RetrievalStrategy | None = None
    ) -> Retriever:
        """Build and cache a reusable retriever for one repository.

        Agents issue many queries per investigation; the snapshot is
        loaded and indexes built once per repository/strategy pair.
        """
        selected = strategy or RetrievalStrategy.HYBRID_GRAPH
        key = (repository, selected.value)
        if key not in self._retrievers:
            snapshot = self.snapshot(repository)
            self._retrievers[key] = build_retriever(
                selected,
                snapshot.chunks,
                self._provider,
                snapshot.vectors,
                expander=self._expander(snapshot),
            )
        return self._retrievers[key]

    def _load(self, repository: str) -> IndexSnapshot:
        spec = RepositorySpec(source=repository)
        repo_id = repository_identifier(spec.source)
        snapshot = self._store.load(repo_id)
        self._check_provider(snapshot)
        return snapshot

    def search(self, request: SearchRequest) -> SearchResponse:
        spec = RepositorySpec(source=request.repository)
        repo_id = repository_identifier(spec.source)
        retriever = self.retriever(request.repository, request.strategy)
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

    def _expander(self, snapshot: IndexSnapshot) -> GraphExpander | None:
        """Build the graph expander when the snapshot carries a graph."""
        if snapshot.graph is None or not snapshot.graph.nodes:
            return None
        store = store_from_snapshot(snapshot.graph)
        chunks_by_qualified = {chunk.qualified_name: chunk for chunk in snapshot.chunks}
        return GraphExpander(store, chunks_by_qualified)

    def _check_provider(self, snapshot: IndexSnapshot) -> None:
        if (
            snapshot.embedding_provider != self._provider.name
            or snapshot.embedding_dimension != self._provider.dimension
        ):
            raise EmbeddingProviderError(
                "Index was built with a different embedding provider; rebuild the index"
            )
