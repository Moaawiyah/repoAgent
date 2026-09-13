"""Deterministic reranking behavior."""

from repoagent.retrieval.models import (
    RetrievalResult,
    RetrievalSource,
    SymbolType,
    make_chunk_id,
)
from repoagent.retrieval.rerank import KeywordOverlapReranker


def make_result(name, source_text, rank, score):
    from repoagent.retrieval.models import CodeChunk

    chunk = CodeChunk(
        chunk_id=make_chunk_id("r", f"{name}.py", name, source_text),
        repository_id="r",
        file_path=f"{name}.py",
        language="python",
        symbol_name=name,
        qualified_name=name,
        symbol_type=SymbolType.FUNCTION,
        start_line=1,
        end_line=1,
        source=source_text,
    )
    return RetrievalResult(
        rank=rank, score=score, source=RetrievalSource.HYBRID, chunk=chunk
    )


CANDIDATES = [
    make_result("unrelated", "def unrelated(): return 42", 1, 0.9),
    make_result(
        "evictor",
        "def evict_expired_entries(max_age): remove stale cache files",
        2,
        0.8,
    ),
    make_result(
        "cache_info",
        "def cache_info(): report cache entry statistics",
        3,
        0.7,
    ),
]


def test_overlap_moves_relevant_candidate_first():
    reranked = KeywordOverlapReranker().rerank(
        "evict expired cache entries", CANDIDATES, top_k=3
    )
    assert reranked[0].chunk.symbol_name == "evictor"
    assert reranked[1].chunk.symbol_name == "cache_info"
    assert reranked[2].chunk.symbol_name == "unrelated"
    assert [result.rank for result in reranked] == [1, 2, 3]


def test_scores_and_provenance_are_preserved_only_rank_changes():
    reranked = KeywordOverlapReranker().rerank("cache", CANDIDATES, 3)
    by_name = {r.chunk.symbol_name: r for r in reranked}
    assert by_name["unrelated"].score == 0.9
    assert by_name["unrelated"].source is RetrievalSource.HYBRID


def test_ties_keep_retrieval_order_and_top_k_applies():
    ties = [
        make_result("one", "def one(): pass", 1, 0.5),
        make_result("two", "def two(): pass", 2, 0.4),
        make_result("three", "def three(): pass", 3, 0.3),
    ]
    reranked = KeywordOverlapReranker().rerank("nothing matches", ties, 2)
    assert [r.chunk.symbol_name for r in reranked] == ["one", "two"]
    assert len(reranked) == 2
