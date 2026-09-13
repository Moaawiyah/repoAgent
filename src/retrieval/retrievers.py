"""Retriever abstraction, vector retrieval, and RRF hybrid fusion."""

from typing import Protocol

from repoagent.retrieval.bm25 import BM25Retriever
from repoagent.retrieval.embeddings import EmbeddingProvider
from repoagent.retrieval.models import (
    CodeChunk,
    RetrievalResult,
    RetrievalSource,
    RetrievalStrategy,
)
from repoagent.retrieval.vector_store import LocalVectorStore, VectorStore


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

    RRF combines ranks instead of raw scores, so incompatible score scales
    are never mixed: ``score(d) = sum over retrievers of 1/(k + rank)``.
    Ties break by chunk identifier, keeping results deterministic.
    """

    def __init__(
        self, lexical: Retriever, semantic: Retriever, rrf_k: int = 60
    ) -> None:
        self._retrievers = (lexical, semantic)
        self._rrf_k = rrf_k

    def search(self, query: str, top_k: int) -> list[RetrievalResult]:
        depth = max(top_k * 2, 10)
        scores: dict[str, float] = {}
        chunks: dict[str, CodeChunk] = {}
        for retriever in self._retrievers:
            for rank, result in enumerate(retriever.search(query, depth), start=1):
                chunk_id = result.chunk.chunk_id
                scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (
                    self._rrf_k + rank
                )
                chunks[chunk_id] = result.chunk
        ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        return [
            RetrievalResult(
                rank=rank,
                score=score,
                source=RetrievalSource.HYBRID,
                chunk=chunks[chunk_id],
            )
            for rank, (chunk_id, score) in enumerate(ordered[:top_k], start=1)
        ]


def build_retriever(
    strategy: RetrievalStrategy,
    chunks: list[CodeChunk],
    provider: EmbeddingProvider,
    vectors: dict[str, list[float]],
) -> Retriever:
    """Materialize the configured strategy from an indexed snapshot.

    Vectors come from the persisted snapshot; chunk embedding never runs
    at query time.
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
    return HybridRetriever(lexical, semantic)
