"""IndexService workflow: chunking, single-pass embedding, persistence."""

import pytest

from repoagent.application.indexing import IndexService
from repoagent.domain.errors import EmbeddingProviderError
from repoagent.domain.repository import RepositorySpec
from repoagent.retrieval.embeddings import HashingEmbeddingProvider


class RecordingStore:
    def __init__(self):
        self.saved = None

    def save(self, snapshot):
        self.saved = snapshot

    def load(self, repo_id): ...

    def exists(self, repo_id):
        return False


class ExplodingProvider:
    name = "exploding"
    dimension = 8

    def embed(self, texts):
        raise RuntimeError("provider outage")


def test_index_persists_snapshot_and_returns_summary(tmp_path):
    (tmp_path / "app.py").write_text("def run():\n    return 1\n")
    store = RecordingStore()
    service = IndexService(store=store, provider=HashingEmbeddingProvider(64))
    summary = service.index(RepositorySpec(source=str(tmp_path)))
    assert summary.chunk_count == 1
    assert summary.python_files == 1
    assert summary.embedding_provider == "hashing"
    assert summary.embedding_dimension == 64
    snapshot = store.saved
    assert snapshot.repo_id == summary.repository_id
    assert set(snapshot.vectors) == {chunk.chunk_id for chunk in snapshot.chunks}
    assert all(len(vector) == 64 for vector in snapshot.vectors.values())


def test_empty_repository_indexes_without_vectors(tmp_path):
    store = RecordingStore()
    summary = IndexService(store=store, provider=HashingEmbeddingProvider(64)).index(
        RepositorySpec(source=str(tmp_path))
    )
    assert summary.chunk_count == 0
    assert store.saved.vectors == {}


def test_provider_failure_is_mapped_to_typed_error(tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n")
    service = IndexService(store=RecordingStore(), provider=ExplodingProvider())
    with pytest.raises(EmbeddingProviderError):
        service.index(RepositorySpec(source=str(tmp_path)))


def test_rankings_do_not_depend_on_checkout_location(tmp_path):
    import shutil
    from pathlib import Path

    from repoagent import RepoAgent, Settings

    fixture = Path(__file__).resolve().parents[1] / "fixtures/rag_repo"
    orders = []
    for location in ("a/deep/place", "b"):
        copy = tmp_path / location / "rag_repo"
        shutil.copytree(fixture, copy)
        client = RepoAgent(settings=Settings(data_dir=tmp_path / location / "data"))
        client.index(copy)
        response = client.search(copy, "session token", strategy="hybrid", top_k=10)
        orders.append([(r.chunk.chunk_id, r.rank) for r in response.results])
    assert orders[0] == orders[1]
