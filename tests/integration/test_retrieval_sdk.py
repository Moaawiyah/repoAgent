"""SDK retrieval behavior: typed results, determinism, and error mapping."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from repoagent import (
    EmbeddingProviderError,
    IndexNotFound,
    RepoAgent,
    RetrievalStrategy,
    SearchResponse,
    Settings,
)
from repoagent.retrieval.embeddings import HashingEmbeddingProvider
from repoagent.retrieval.persistence import IndexSummary

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "rag_repo"
CASES = Path(__file__).resolve().parents[1] / "fixtures" / "rag_cases.json"


def client(tmp_path, **kwargs):
    return RepoAgent(settings=Settings(data_dir=tmp_path / "data"), **kwargs)


def test_index_and_search_return_typed_results(tmp_path):
    agent = client(tmp_path)
    summary = agent.index(FIXTURE)
    assert isinstance(summary, IndexSummary)
    assert summary.chunk_count > 0
    response = agent.search(FIXTURE, "verify password", top_k=3)
    assert isinstance(response, SearchResponse)
    assert response.strategy is RetrievalStrategy.HYBRID
    assert len(response.results) <= 3
    chunk = response.results[0].chunk
    assert chunk.file_path and chunk.qualified_name and chunk.source


def test_reindexing_is_idempotent(tmp_path):
    agent = client(tmp_path)
    first = agent.index(FIXTURE)
    second = agent.index(FIXTURE)
    assert first == second
    hits = [r.chunk.chunk_id for r in agent.search(FIXTURE, "tokens", top_k=5).results]
    again = agent.search(FIXTURE, "tokens", top_k=5).results
    assert hits == [r.chunk.chunk_id for r in again]


def test_search_without_index_raises_typed_error(tmp_path):
    with pytest.raises(IndexNotFound):
        client(tmp_path).search(FIXTURE, "anything")


def test_provider_mismatch_is_detected(tmp_path):
    agent = client(tmp_path)
    agent.index(FIXTURE)
    mismatched = client(tmp_path, embedding_provider=HashingEmbeddingProvider(128))
    with pytest.raises(EmbeddingProviderError):
        mismatched.search(FIXTURE, "anything")


def test_invalid_sources_and_queries_are_rejected(tmp_path):
    agent = client(tmp_path)
    with pytest.raises(ValidationError):
        agent.index(tmp_path / "missing")
    with pytest.raises(ValidationError):
        agent.search(FIXTURE, "   ")
    assert not (tmp_path / "data").exists()


def test_evaluation_through_the_facade(tmp_path):
    from repoagent.evaluation.models import RetrievalCase

    agent = client(tmp_path)
    agent.index(FIXTURE)
    cases = [
        RetrievalCase.model_validate(item)
        for item in json.loads(CASES.read_text(encoding="utf-8"))
    ]
    report = agent.evaluate(FIXTURE, cases, k=5)
    assert report.repository.endswith("rag_repo")
    assert len(report.rows) == 4
    assert all(0.0 <= row.recall_at_k <= 1.0 for row in report.rows)
