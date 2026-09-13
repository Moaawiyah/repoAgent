"""Deterministic hashing embeddings and the local vector store."""

import pytest

from repoagent.config import Settings
from repoagent.retrieval.embeddings import (
    HashingEmbeddingProvider,
    provider_from_settings,
)
from repoagent.retrieval.vector_store import LocalVectorStore


def norm(vector):
    return sum(value * value for value in vector) ** 0.5


def test_embeddings_are_deterministic_and_normalized():
    provider = HashingEmbeddingProvider(64)
    first = provider.embed(["verify_password credentials"])
    second = provider.embed(["verify_password credentials"])
    assert first == second
    assert norm(first[0]) == pytest.approx(1.0)
    assert provider.name == "hashing"


def test_different_texts_embed_differently_and_batch_together():
    provider = HashingEmbeddingProvider(64)
    one, two = provider.embed(["invoice total", "cache eviction"])
    assert one != two
    assert len(provider.embed(["a", "b", "c"])) == 3


def test_similar_subwords_share_similarity_signal():
    provider = HashingEmbeddingProvider(256)
    base, variant, unrelated = provider.embed(
        ["credentials", "credential", "inventory"]
    )

    def dot(a, b):
        return sum(x * y for x, y in zip(a, b, strict=True))

    assert dot(base, variant) > dot(base, unrelated)


def test_provider_from_settings_uses_configuration():
    provider = provider_from_settings(Settings(embedding_dimension=128))
    assert provider.dimension == 128
    assert len(provider.embed(["x"])[0]) == 128


def test_empty_text_yields_zero_vector():
    provider = HashingEmbeddingProvider(32)
    assert provider.embed([""])[0] == [0.0] * 32


def test_vector_store_similarity_search_and_top_k():
    store = LocalVectorStore()
    store.add("near", [1.0, 0.0])
    store.add("far", [0.0, 1.0])
    store.add("close", [0.9, 0.1])
    assert len(store) == 3
    hits = store.search([1.0, 0.0], 2)
    assert [chunk_id for chunk_id, _ in hits] == ["near", "close"]
    assert hits[0][1] == pytest.approx(1.0)
    everything = store.search([1.0, 0.0], 10)
    assert len(everything) == 3
    assert everything[:2] == hits


def test_vector_store_empty_and_clear_behavior():
    store = LocalVectorStore()
    assert store.search([1.0, 0.0], 5) == []
    store.add("a", [1.0])
    store.clear()
    assert len(store) == 0
    assert store.search([1.0], 5) == []
