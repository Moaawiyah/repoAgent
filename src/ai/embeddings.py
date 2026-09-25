"""OpenAI-compatible semantic embeddings; no vendor types escape this module.

Serves OpenAI itself and any server speaking ``POST /v1/embeddings``
(Ollama, vLLM, LM Studio, text-embeddings-inference) via
``REPOAGENT_EMBEDDING_BASE_URL``. Retrieval depends only on the
``EmbeddingProvider`` protocol, never on this adapter.
"""

import logging
from collections.abc import Callable
from typing import Any

from repoagent.config import Settings
from repoagent.domain.errors import EmbeddingProviderError

LOGGER = logging.getLogger(__name__)
ClientFactory = Callable[[Settings], Any]
MAX_INPUT_CHARS = 6000
MIN_INPUT_CHARS = 250
PRECISION = 6


def _openai_client(settings: Settings) -> Any:
    from openai import OpenAI

    key = settings.embedding_api_key or settings.llm_api_key
    return OpenAI(
        # Local servers (Ollama, vLLM) ignore the key, but the SDK requires one.
        api_key=key.get_secret_value() if key else "unused",
        base_url=settings.embedding_base_url,
        timeout=settings.embedding_timeout,
        max_retries=2,
    )


class OpenAIEmbeddingProvider:
    """Batched semantic embeddings with a model-qualified identity.

    ``name`` includes the model, so an index built with one model is
    rejected by a search configured for another. The vector dimension is
    a property of the model, so it is probed once on first use instead of
    being configured by hand.

    Token-dense inputs (numeric tables, minified data) can exceed a local
    server's per-input token budget even under ``MAX_INPUT_CHARS``. A failed
    batch is retried item by item, and a failing item is halved until it
    fits; ``truncated`` counts those inputs so degradation is observable.
    """

    def __init__(
        self, settings: Settings, client_factory: ClientFactory | None = None
    ) -> None:
        if settings.embedding_base_url is None and not (
            settings.embedding_api_key or settings.llm_api_key
        ):
            raise EmbeddingProviderError(
                "Semantic embeddings need REPOAGENT_EMBEDDING_BASE_URL or an API key"
            )
        self.name = f"openai:{settings.embedding_model}"
        self._settings = settings
        self._factory = client_factory or _openai_client
        self._client: Any = None
        self._dimension: int | None = None
        self.truncated = 0

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            self._dimension = len(self._request(["dimension probe"])[0])
        return self._dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed in configured batches; output order matches input order."""
        size = self._settings.embedding_batch_size
        vectors: list[list[float]] = []
        for start in range(0, len(texts), size):
            vectors.extend(self._request(texts[start : start + size]))
        if vectors:
            self._check_dimension(len(vectors[0]))
        return vectors

    def _check_dimension(self, found: int) -> None:
        if self._dimension is None:
            self._dimension = found
        elif found != self._dimension:
            raise EmbeddingProviderError("Embedding model changed vector dimension")

    def _request(self, batch: list[str]) -> list[list[float]]:
        from openai import APIError, BadRequestError

        if self._client is None:
            self._client = self._factory(self._settings)
        inputs = [text[:MAX_INPUT_CHARS] or " " for text in batch]
        try:
            response = self._client.embeddings.create(
                model=self._settings.embedding_model, input=inputs
            )
        except BadRequestError:
            return self._degrade(inputs)
        except APIError:
            LOGGER.warning("Embedding request failed", extra={"event": "embed_failed"})
            raise EmbeddingProviderError(
                "Embedding request failed; check the embedding endpoint and model"
            ) from None
        ordered = sorted(response.data, key=lambda item: item.index)
        if len(ordered) != len(inputs):
            raise EmbeddingProviderError("Embedding response size mismatch")
        # Rounding keeps persisted JSON indexes compact without changing ranks.
        return [[round(v, PRECISION) for v in item.embedding] for item in ordered]

    def _degrade(self, inputs: list[str]) -> list[list[float]]:
        if len(inputs) > 1:
            return [vector for text in inputs for vector in self._request([text])]
        text = inputs[0]
        if len(text) <= MIN_INPUT_CHARS:
            LOGGER.warning("Embedding request failed", extra={"event": "embed_failed"})
            raise EmbeddingProviderError(
                "Embedding request failed; check the embedding endpoint and model"
            )
        self.truncated += 1
        LOGGER.warning("Embedding input truncated", extra={"event": "embed_truncated"})
        return self._request([text[: len(text) // 2]])
