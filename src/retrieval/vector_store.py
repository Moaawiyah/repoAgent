"""Vector store abstraction with a local in-memory implementation."""

import math
from collections.abc import Sequence
from typing import Protocol


class VectorStore(Protocol):
    """Chunk-agnostic similarity search over stored vectors.

    A production pgvector/Qdrant adapter can implement this protocol
    without changing retrieval or application code.
    """

    def add(self, chunk_id: str, vector: Sequence[float]) -> None: ...

    def search(
        self, vector: Sequence[float], top_k: int
    ) -> list[tuple[str, float]]: ...

    def clear(self) -> None: ...

    def __len__(self) -> int: ...


class LocalVectorStore:
    """Cosine similarity over in-memory vectors with stable ordering."""

    def __init__(self) -> None:
        self._vectors: dict[str, tuple[float, ...]] = {}

    def add(self, chunk_id: str, vector: Sequence[float]) -> None:
        self._vectors[chunk_id] = tuple(float(value) for value in vector)

    def clear(self) -> None:
        self._vectors.clear()

    def __len__(self) -> int:
        return len(self._vectors)

    def search(self, vector: Sequence[float], top_k: int) -> list[tuple[str, float]]:
        if top_k <= 0 or not self._vectors:
            return []
        query = tuple(float(value) for value in vector)
        scored = [
            (chunk_id, _cosine(query, stored))
            for chunk_id, stored in self._vectors.items()
        ]
        scored.sort(key=lambda item: (-item[1], item[0]))
        return scored[:top_k]


def _cosine(first: tuple[float, ...], second: tuple[float, ...]) -> float:
    norm_first = math.sqrt(sum(value * value for value in first))
    norm_second = math.sqrt(sum(value * value for value in second))
    if not norm_first or not norm_second:
        return 0.0
    pairs = zip(first, second, strict=True)
    return sum(a * b for a, b in pairs) / (norm_first * norm_second)
