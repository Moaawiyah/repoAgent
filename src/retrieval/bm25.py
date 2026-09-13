"""BM25 lexical retrieval over code chunks."""

import math
from collections import Counter

from repoagent.retrieval.models import CodeChunk, RetrievalResult, RetrievalSource
from repoagent.retrieval.tokenize import tokenize


class BM25Index:
    """Okapi BM25 scoring with deterministic, stable ordering.

    Documents are chunk search texts; ties break by chunk identifier so
    repeated runs against unchanged repositories rank identically.
    """

    def __init__(
        self, chunks: list[CodeChunk], k1: float = 1.5, b: float = 0.75
    ) -> None:
        self._k1 = k1
        self._b = b
        self._chunks = sorted(chunks, key=lambda chunk: chunk.chunk_id)
        self._documents = [
            Counter(tokenize(chunk.search_text)) for chunk in self._chunks
        ]
        self._lengths = [sum(doc.values()) for doc in self._documents]
        self._average = (
            sum(self._lengths) / len(self._lengths) if self._lengths else 0.0
        )
        self._idf = self._idf_weights()

    def _idf_weights(self) -> dict[str, float]:
        frequency: Counter[str] = Counter()
        for document in self._documents:
            frequency.update(document.keys())
        total = len(self._chunks)
        return {
            term: math.log((total - count + 0.5) / (count + 0.5) + 1.0)
            for term, count in frequency.items()
        }

    def search(self, query: str, top_k: int) -> list[tuple[CodeChunk, float]]:
        """Return the top-k chunks with positive BM25 scores."""
        terms = tokenize(query)
        if not terms or not self._chunks or top_k <= 0:
            return []
        scored: list[tuple[CodeChunk, float]] = []
        for chunk, document, length in zip(
            self._chunks, self._documents, self._lengths, strict=True
        ):
            score = self._score(terms, document, length)
            if score > 0.0:
                scored.append((chunk, score))
        scored.sort(key=lambda item: (-item[1], item[0].chunk_id))
        return scored[:top_k]

    def _score(self, terms: list[str], document: Counter, length: int) -> float:
        score = 0.0
        for term in terms:
            frequency = document.get(term, 0)
            if not frequency:
                continue
            normalizer = self._k1 * (1.0 - self._b + self._b * length / self._average)
            score += (
                self._idf.get(term, 0.0)
                * frequency
                * (self._k1 + 1.0)
                / (frequency + normalizer)
            )
        return score


class BM25Retriever:
    """Retriever adapter exposing BM25 ranking as structured results."""

    def __init__(self, chunks: list[CodeChunk]) -> None:
        self._index = BM25Index(chunks)

    def search(self, query: str, top_k: int) -> list[RetrievalResult]:
        return [
            RetrievalResult(
                rank=rank,
                score=score,
                source=RetrievalSource.BM25,
                chunk=chunk,
            )
            for rank, (chunk, score) in enumerate(
                self._index.search(query, top_k), start=1
            )
        ]
