"""Retriever abstraction, vector retrieval, and hybrid fusion."""

from typing import TYPE_CHECKING, Protocol

from repoagent.retrieval.bm25 import BM25Retriever
from repoagent.retrieval.embeddings import EmbeddingProvider
from repoagent.retrieval.fusion import rrf_fuse
from repoagent.retrieval.models import (
    CodeChunk,
    Evidence,
    RetrievalResult,
    RetrievalSource,
    RetrievalStrategy,
)
from repoagent.retrieval.vector_store import LocalVectorStore, VectorStore

if TYPE_CHECKING:
    from repoagent.graph.expansion import GraphExpander
    from repoagent.graph.policy import GraphPolicy


class Retriever(Protocol):
    """A strategy that turns a query into ranked, provenance-backed hits."""

    def search(self, query: str, top_k: int) -> list[RetrievalResult]: ...


class VectorRetriever:
    """Embeds the query once and searches a prepared vector store."""

    def __init__(
        self,
        provider: EmbeddingProvider,
        store: VectorStore,
        chunks_by_id: dict[str, CodeChunk],
    ) -> None:
        self._provider = provider
        self._store = store
        self._chunks = chunks_by_id

    def search(self, query: str, top_k: int) -> list[RetrievalResult]:
        vector = self._provider.embed([query])[0]
        results: list[RetrievalResult] = []
        for rank, (chunk_id, score) in enumerate(
            self._store.search(vector, top_k), start=1
        ):
            chunk = self._chunks.get(chunk_id)
            if chunk is not None:
                results.append(
                    RetrievalResult(
                        rank=rank,
                        score=score,
                        source=RetrievalSource.VECTOR,
                        chunk=chunk,
                    )
                )
        return results


class HybridRetriever:
    """Fuses lexical and semantic rankings with Reciprocal Rank Fusion.

    Per-source ranks are preserved as structured evidence so consumers can
    explain which retriever found each result and at which rank.
    """

    def __init__(
        self, lexical: Retriever, semantic: Retriever, rrf_k: int = 60
    ) -> None:
        self._retrievers = (lexical, semantic)
        self._rrf_k = rrf_k

    def search(self, query: str, top_k: int) -> list[RetrievalResult]:
        depth = max(top_k * 2, 10)
        ranked: list[list[RetrievalResult]] = []
        for retriever in self._retrievers:
            results = retriever.search(query, depth)
            ranked.append(
                [
                    result.model_copy(
                        update={
                            "evidence": [Evidence(kind=result.source.value, rank=rank)]
                        }
                    )
                    for rank, result in enumerate(results, start=1)
                ]
            )
        return rrf_fuse(ranked, self._rrf_k)[:top_k]


def build_retriever(
    strategy: RetrievalStrategy,
    chunks: list[CodeChunk],
    provider: EmbeddingProvider,
    vectors: dict[str, list[float]],
    expander: "GraphExpander | None" = None,
    policy: "GraphPolicy | None" = None,
) -> Retriever:
    """Materialize the configured strategy from an indexed snapshot.

    Vectors come from the persisted snapshot; chunk embedding never runs
    at query time. ``expander`` (a GraphExpander) is required only for
    the hybrid_graph strategy; ``policy`` (a GraphPolicy) tunes it.
    """
    lexical = BM25Retriever(chunks)
    if strategy is RetrievalStrategy.BM25:
        return lexical
    store = LocalVectorStore()
    for chunk_id, vector in vectors.items():
        store.add(chunk_id, vector)
    semantic = VectorRetriever(
        provider, store, {chunk.chunk_id: chunk for chunk in chunks}
    )
    if strategy is RetrievalStrategy.VECTOR:
        return semantic
    from repoagent.retrieval.graph import build_graph_retriever

    hybrid = HybridRetriever(lexical, semantic)
    return build_graph_retriever(strategy, hybrid, expander, policy)
