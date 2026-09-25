"""OpenAI-compatible semantic embeddings, exercised offline with a fake client."""

from types import SimpleNamespace

import pytest

from repoagent.ai import embeddings as module
from repoagent.ai.embeddings import OpenAIEmbeddingProvider
from repoagent.config import Settings
from repoagent.domain.errors import EmbeddingProviderError
from repoagent.retrieval.embeddings import provider_from_settings

LOCAL = {"embedding_provider": "openai", "embedding_base_url": "http://local/v1"}


class FakeEmbeddings:
    def __init__(self, dimension=3, fail=False, drop=False, limit=None):
        self.calls, self._dimension, self._fail, self._drop = [], dimension, fail, drop
        self._limit = limit

    def create(self, model, input):
        import httpx
        from openai import APIError, BadRequestError

        self.calls.append((model, list(input)))
        if self._fail:
            raise APIError("boom", request=None, body=None)
        if self._limit and any(len(text) > self._limit for text in input):
            request = httpx.Request("POST", "http://local/v1/embeddings")
            response = httpx.Response(400, request=request)
            raise BadRequestError("too long", response=response, body=None)
        items = [
            SimpleNamespace(index=i, embedding=[len(text) / 3.0] * self._dimension)
            for i, text in enumerate(input)
        ]
        items = items[1:] if self._drop else items
        return SimpleNamespace(data=list(reversed(items)))


def provider(fake, **overrides):
    settings = Settings(**{**LOCAL, "embedding_batch_size": 2, **overrides})
    client = SimpleNamespace(embeddings=fake)
    return OpenAIEmbeddingProvider(settings, client_factory=lambda _: client)


def test_batches_preserve_order_and_round_values():
    fake = FakeEmbeddings()
    vectors = provider(fake).embed(["a", "bb", "ccc", "d" * 10_000])
    assert [len(call[1]) for call in fake.calls] == [2, 2]
    assert vectors[0] == [0.333333] * 3 and vectors[2] == [1.0] * 3
    assert len(fake.calls[1][1][1]) == module.MAX_INPUT_CHARS


def test_name_is_model_qualified_and_dimension_probed_once():
    fake = FakeEmbeddings(dimension=5)
    semantic = provider(fake, embedding_model="nomic-embed-text")
    assert semantic.name == "openai:nomic-embed-text"
    assert semantic.dimension == 5 and semantic.dimension == 5
    assert len(fake.calls) == 1
    assert semantic.embed([]) == []


def test_api_failures_become_typed_errors():
    with pytest.raises(EmbeddingProviderError, match="endpoint"):
        provider(FakeEmbeddings(fail=True)).embed(["x"])
    with pytest.raises(EmbeddingProviderError, match="size"):
        provider(FakeEmbeddings(drop=True)).embed(["x", "y"])


def test_dimension_change_is_rejected():
    fake = FakeEmbeddings(dimension=4)
    semantic = provider(fake)
    semantic.embed(["x"])
    fake._dimension = 8
    with pytest.raises(EmbeddingProviderError, match="dimension"):
        semantic.embed(["y"])


def test_settings_select_semantic_provider_and_require_endpoint():
    assert isinstance(
        provider_from_settings(Settings(**LOCAL)), OpenAIEmbeddingProvider
    )
    assert provider_from_settings(Settings()).name == "hashing"
    with pytest.raises(EmbeddingProviderError):
        provider_from_settings(Settings(embedding_provider="openai"))


def test_default_client_uses_configured_endpoint_without_leaking_key():
    settings = Settings(**LOCAL, embedding_api_key="sk-secret", embedding_timeout=7)
    client = module._openai_client(settings)
    assert str(client.base_url).startswith("http://local/v1")
    assert client.timeout == 7 and client.api_key == "sk-secret"
    assert module._openai_client(Settings(**LOCAL)).api_key == "unused"


def test_token_dense_inputs_are_retried_alone_and_halved():
    fake = FakeEmbeddings(limit=1000)
    semantic = provider(fake)
    vectors = semantic.embed(["short", "9" * 3000])
    assert len(vectors) == 2 and semantic.truncated == 2
    assert [len(call[1][0]) for call in fake.calls[1:]] == [5, 3000, 1500, 750]
    with pytest.raises(EmbeddingProviderError):
        provider(FakeEmbeddings(limit=100)).embed(["9" * 300])
