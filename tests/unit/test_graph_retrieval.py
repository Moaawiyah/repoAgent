"""Graph retrieval: expansion, fusion reuse, evidence, and provenance."""

from pathlib import Path

import pytest

from repoagent.analysis.analyzer import RepositoryAnalyzer
from repoagent.domain.errors import RetrievalError
from repoagent.domain.repository import RepositorySpec
from repoagent.graph.builder import RepositoryGraphBuilder
from repoagent.graph.expansion import GraphExpander
from repoagent.graph.store import store_from_snapshot
from repoagent.graph.traversal import TraversalConfig
from repoagent.retrieval.chunking import CodeChunker
from repoagent.retrieval.graph import HybridGraphRetriever, build_graph_retriever
from repoagent.retrieval.models import (
    RetrievalResult,
    RetrievalSource,
    RetrievalStrategy,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "rag_repo"


class FakeHybrid:
    """Scripted seed ranking for deterministic tests."""

    def __init__(self, chunks, names):
        self._chunks = chunks
        self._names = names

    def search(self, query, top_k):
        return [
            RetrievalResult(
                rank=rank,
                score=1.0 / rank,
                source=RetrievalSource.HYBRID,
                chunk=self._chunks[qualified],
            )
            for rank, qualified in enumerate(self._names[:top_k], start=1)
        ]


def prepare():
    analysis = RepositoryAnalyzer().analyze(RepositorySpec(source=str(FIXTURE)))
    chunks = CodeChunker("repo").chunk(analysis, FIXTURE.resolve())
    graph = RepositoryGraphBuilder(chunks).build(analysis).to_snapshot()
    store = store_from_snapshot(graph)
    by_qualified = {chunk.qualified_name: chunk for chunk in chunks}
    return store, chunks, by_qualified


def test_expansion_follows_call_chain_with_provenance():
    store, chunks, by_qualified = prepare()
    expander = GraphExpander(store, chunks, TraversalConfig(max_depth=3))
    seed = RetrievalResult(
        rank=1,
        score=1.0,
        source=RetrievalSource.HYBRID,
        chunk=by_qualified["auth.controller.AuthController.login"],
    )
    candidates = expander.expand([seed], top_k=10)
    verified = {result.chunk.qualified_name: result for result in candidates}
    target = verified["auth.service.AuthService.verify_password"]
    assert target.source is RetrievalSource.GRAPH
    graph_note = next(note for note in target.evidence if note.kind == "graph")
    assert graph_note.distance == 2
    assert [hop.relation for hop in graph_note.path] == ["calls", "calls"]
    assert graph_note.path[0].source_symbol.endswith("login")


def test_hybrid_graph_fuses_seeds_and_expansion():
    store, chunks, by_qualified = prepare()
    expander = GraphExpander(store, chunks)
    retriever = HybridGraphRetriever(
        FakeHybrid(by_qualified, ["auth.controller.AuthController.login"]), expander
    )
    results = retriever.search("login", top_k=5)
    assert results
    assert all(r.source is RetrievalSource.HYBRID_GRAPH for r in results)
    assert [r.rank for r in results] == list(range(1, len(results) + 1))
    seed_hit = next(
        r
        for r in results
        if r.chunk.qualified_name == "auth.controller.AuthController.login"
    )
    assert any(note.kind == "hybrid_seed" for note in seed_hit.evidence)
    first_run = [r.chunk.chunk_id for r in results]
    assert first_run == [r.chunk.chunk_id for r in retriever.search("login", top_k=5)]


def test_missing_graph_data_is_a_typed_error():
    with pytest.raises(RetrievalError):
        build_graph_retriever(
            RetrievalStrategy.HYBRID_GRAPH,
            FakeHybrid({}, []),
            expander=None,
        )


def test_hybrid_strategy_passes_through():
    hybrid = FakeHybrid({}, [])
    assert (
        build_graph_retriever(RetrievalStrategy.HYBRID, hybrid, expander=None) is hybrid
    )
