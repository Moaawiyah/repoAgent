"""Configured retrieval paths: rerank pools, LLM rerank arms, legacy indexes."""

from pathlib import Path

import pytest

from repoagent import RepoAgent, Settings
from repoagent.adapters.index_store import JsonIndexStore
from repoagent.analysis.analyzer import RepositoryAnalyzer
from repoagent.application.indexing import IndexService
from repoagent.application.search_factory import configured_search
from repoagent.benchmark.provenance import _embedding
from repoagent.domain.errors import LLMError, RepoAgentError
from repoagent.domain.repository import RepositorySpec
from repoagent.graph.builder import RepositoryGraphBuilder
from repoagent.graph.expansion import GraphExpander
from repoagent.graph.models import EdgeType
from repoagent.graph.scoring import ScoringConfig
from repoagent.graph.store import store_from_snapshot
from repoagent.retrieval.chunking import CodeChunker
from repoagent.retrieval.embeddings import HashingEmbeddingProvider
from repoagent.retrieval.models import RetrievalResult, RetrievalSource, SearchRequest
from repoagent.workflows.guards import required
from tests.support.scripted import ScriptedLLMProvider

ROOT = Path(__file__).resolve().parents[2]
RAG = ROOT / "tests/fixtures/rag_repo"


class SpyReranker:
    def __init__(self):
        self.pool = 0

    def rerank(self, query, candidates, top_k):
        self.pool = len(candidates)
        return candidates[:top_k]


def indexed(tmp_path):
    store, provider = JsonIndexStore(tmp_path / "idx"), HashingEmbeddingProvider()
    IndexService(store, provider).index(RepositorySpec(source=str(RAG)))
    return store, provider


def test_rerank_pool_widens_candidates_only_when_configured(tmp_path):
    store, provider = indexed(tmp_path)
    request = SearchRequest(repository=str(RAG), query="password", top_k=2, rerank=True)
    for pool, expected in ((7, 7), (None, 2)):
        spy = SpyReranker()
        service = configured_search(
            Settings(), store, provider, reranker=spy, rerank_candidates=pool
        )
        assert len(service.search(request).results) == 2 and spy.pool == expected


def test_llm_reranker_from_settings_needs_a_provider(tmp_path):
    store, provider = indexed(tmp_path)
    with pytest.raises(LLMError):
        configured_search(Settings(), store, provider, reranker="llm")


def test_llm_rerank_arm_records_token_usage(tmp_path):
    ranked = [{"ranked_ids": ["c2", "c1"]}] * 3
    benchmarks = RepoAgent(settings=Settings(data_dir=tmp_path / "data")).benchmarks()
    run = benchmarks.run(
        ROOT / "benchmarks/fixtures.json",
        ablations=["rerank_llm"],
        task_ids=["auth-uppercase-email"],
        provider=ScriptedLLMProvider(ranked),
    )
    (result,) = benchmarks.load(run.manifest.run_id).results
    assert result.tokens.llm_calls == 3
    assert set(result.retrieval) == {"bm25", "hybrid", "hybrid_graph"}


def test_expander_maps_indexes_built_before_node_identity():
    analysis = RepositoryAnalyzer().analyze(RepositorySpec(source=str(RAG)))
    chunks = CodeChunker("repo").chunk(analysis, RAG.resolve())
    snapshot = RepositoryGraphBuilder().build(analysis).to_snapshot()
    legacy = [chunk.model_copy(update={"node_id": None}) for chunk in chunks]
    store = store_from_snapshot(snapshot)
    by_name = {chunk.qualified_name: chunk for chunk in legacy}
    seed = by_name["auth.controller.AuthController.login"]
    orphan = seed.model_copy(update={"qualified_name": "gone", "chunk_id": "x"})
    seeds = [
        RetrievalResult(rank=i, score=1.0, source=RetrievalSource.HYBRID, chunk=c)
        for i, c in enumerate([orphan, seed], start=1)
    ]
    found = GraphExpander(store, legacy).expand(seeds, 10)
    assert found and all(r.chunk.node_id is None for r in found)
    muted = ScoringConfig(weights={edge: 0.0 for edge in EdgeType})
    assert GraphExpander(store, legacy, scoring=muted).expand(seeds, 10) == []


def test_guards_and_semantic_provenance():
    assert required(1, "x") == 1
    with pytest.raises(RepoAgentError, match="missing handle"):
        required(None, "handle")
    semantic = Settings(embedding_provider="openai", embedding_model="nomic")
    assert _embedding(semantic) == "openai:nomic"
    assert _embedding(Settings()) == "hashing:256"
