"""Embedding provider abstraction with a deterministic local provider."""

import hashlib
from typing import Protocol

from repoagent.config import Settings
from repoagent.retrieval.tokenize import tokenize

TRIGRAM_WEIGHT = 0.35


class EmbeddingProvider(Protocol):
    """Vendor-independent embedding contract.

    Concrete providers own model identity; the rest of RepoAgent depends
    only on this protocol, so provider-backed semantic embeddings can be
    added without touching retrieval code.
    """

    name: str
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashingEmbeddingProvider:
    """Deterministic offline provider over hashed tokens and trigrams.

    Captures lexical and sub-word similarity (for example ``credentials``
    vs ``credential``) with no network access. Intended for local
    development, tests, and as the configured default provider.
    """

    def __init__(self, dimension: int = 256) -> None:
        self.name = "hashing"
        self.dimension = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed each text once; callers must batch to avoid rework."""
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in sorted(set(tokenize(text))):
            self._add(vector, token, 1.0)
            for trigram in _trigrams(token):
                self._add(vector, trigram, TRIGRAM_WEIGHT)
        return _normalize(vector)

    def _add(self, vector: list[float], term: str, weight: float) -> None:
        digest = hashlib.blake2b(term.encode(), digest_size=8).digest()
        index = int.from_bytes(digest, "big") % self.dimension
        vector[index] += weight


def _trigrams(token: str) -> list[str]:
    padded = f"<{token}>"
    if len(padded) < 4:
        return []
    return [padded[index : index + 3] for index in range(len(padded) - 2)]


def _normalize(vector: list[float]) -> list[float]:
    norm = sum(value * value for value in vector) ** 0.5
    return [value / norm for value in vector] if norm else vector


def provider_from_settings(settings: Settings) -> EmbeddingProvider:
    """Build the embedding provider selected by configuration."""
    if settings.embedding_provider != "hashing":
        raise ValueError(f"Unknown embedding provider: {settings.embedding_provider}")
    return HashingEmbeddingProvider(settings.embedding_dimension)
