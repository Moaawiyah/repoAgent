"""Hybrid RRF fusion, vector retrieval, and strategy materialization."""

from repoagent.retrieval.bm25 import BM25Retriever
from repoagent.retrieval.embeddings import HashingEmbeddingProvider
from repoagent.retrieval.models import (
    CodeChunk,
    RetrievalResult,
    RetrievalSource,
    RetrievalStrategy,
    SymbolType,
)
from repoagent.retrieval.retrievers import (
    HybridRetriever,
    VectorRetriever,
    build_retriever,
)


def chunk(name):
    return CodeChunk(
        chunk_id=f"id-{name}",
        repository_id="r",
        file_path=f"{name}.py",
        language="python",
        symbol_name=name,
        qualified_name=name,
        symbol_type=SymbolType.FUNCTION,
        start_line=1,
        end_line=1,
        source=f"def {name}(): pass",
    )


CHUNKS = {name: chunk(name) for name in ("alpha", "beta", "gamma", "delta")}


class FakeRetriever:
    def __init__(self, *names):
        self._names = names

    def search(self, query, top_k):
        return [
            RetrievalResult(
                rank=rank,
                score=1.0 / rank,
                source=RetrievalSource.BM25,
                chunk=CHUNKS[name],
            )
            for rank, name in enumerate(self._names[:top_k], start=1)
        ]


def make_result(name, rank, source=RetrievalSource.BM25, score=1.0):
    return RetrievalResult(rank=rank, score=score, source=source, chunk=CHUNKS[name])


def test_rrf_fuses_ranks_with_expected_scores():
    hybrid = HybridRetriever(
        FakeRetriever("alpha", "beta", "gamma"),
        FakeRetriever("gamma", "delta", "alpha"),
        rrf_k=1,
    )
    results = hybrid.search("anything", top_k=4)
    names = [r.chunk.symbol_name for r in results]
    assert names == ["alpha", "gamma", "beta", "delta"]
    scores = {r.chunk.symbol_name: r.score for r in results}
    assert scores == {
        "alpha": 1 / 2 + 1 / 4,
        "gamma": 1 / 4 + 1 / 2,
        "beta": 1 / 3,
        "delta": 1 / 3,
    }
    assert all(r.source is RetrievalSource.HYBRID for r in results)


def test_duplicates_are_fused_and_ties_are_deterministic():
    hybrid = HybridRetriever(
        FakeRetriever("beta", "alpha"), FakeRetriever("gamma", "delta"), rrf_k=1
    )
    first = hybrid.search("q", 4)
    second = hybrid.search("q", 4)
    names = [r.chunk.symbol_name for r in first]
    assert len(names) == len(set(names))
    assert [(r.chunk.chunk_id, r.score) for r in first] == [
        (r.chunk.chunk_id, r.score) for r in second
    ]
    assert [r.rank for r in first] == [1, 2, 3, 4]


def test_top_k_and_provenance_are_preserved():
    hybrid = HybridRetriever(FakeRetriever("alpha", "beta"), FakeRetriever("gamma"))
    results = hybrid.search("q", top_k=2)
    assert len(results) == 2
    for result in results:
        assert result.chunk.file_path.endswith(".py")
        assert result.chunk.source


def test_vector_retriever_embeds_query_and_maps_chunks():
    provider = HashingEmbeddingProvider(32)
    store = _prepared_store(provider)
    by_id = {instance.chunk_id: instance for instance in CHUNKS.values()}
    retriever = VectorRetriever(provider, store, by_id)
    results = retriever.search("alpha", 2)
    assert len(results) == 2
    assert all(r.source is RetrievalSource.VECTOR for r in results)
    assert all(r.chunk.chunk_id.startswith("id-") for r in results)


def _prepared_store(provider):
    from repoagent.retrieval.vector_store import LocalVectorStore

    store = LocalVectorStore()
    for instance in CHUNKS.values():
        store.add(instance.chunk_id, provider.embed([instance.search_text])[0])
    return store


def test_build_retriever_materializes_each_strategy():
    provider = HashingEmbeddingProvider(32)
    vectors = {
        instance.chunk_id: provider.embed([instance.search_text])[0]
        for instance in CHUNKS.values()
    }
    listed = list(CHUNKS.values())
    lexical = build_retriever(RetrievalStrategy.BM25, listed, provider, vectors)
    assert isinstance(lexical, BM25Retriever)
    semantic = build_retriever(RetrievalStrategy.VECTOR, listed, provider, vectors)
    assert isinstance(semantic, VectorRetriever)
    hybrid = build_retriever(RetrievalStrategy.HYBRID, listed, provider, vectors)
    assert isinstance(hybrid, HybridRetriever)
    assert hybrid.search("alpha", 3)
    assert lexical.search("alpha", 1)
    empty = build_retriever(RetrievalStrategy.VECTOR, listed, provider, {})
    assert empty.search("alpha", 3) == []
