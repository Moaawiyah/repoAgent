"""Optional deterministic reranking of retrieval candidates."""

from typing import Protocol

from repoagent.retrieval.models import RetrievalResult
from repoagent.retrieval.tokenize import tokenize


class Reranker(Protocol):
    """Reorders a candidate set and returns at most ``top_k`` of it.

    Implementations never add candidates and keep provenance intact. The
    keyword reranker is deterministic and used in tests; model-backed ones
    live in :mod:`repoagent.retrieval.model_rerank`.
    """

    def rerank(
        self, query: str, candidates: list[RetrievalResult], top_k: int
    ) -> list[RetrievalResult]: ...


class KeywordOverlapReranker:
    """Reranks candidates by query-term overlap with chunk content.

    A simple, fully local reranker: candidates sharing more distinct
    query terms move up, and ties keep the retrieval order. Provenance is
    preserved untouched; only rank changes.
    """

    def rerank(
        self, query: str, candidates: list[RetrievalResult], top_k: int
    ) -> list[RetrievalResult]:
        terms = set(tokenize(query))
        scored = [
            (
                -len(terms & set(tokenize(candidate.chunk.search_text))),
                position,
                candidate,
            )
            for position, candidate in enumerate(candidates)
        ]
        scored.sort(key=lambda item: (item[0], item[1]))
        return [
            RetrievalResult(
                rank=rank,
                score=candidate.score,
                source=candidate.source,
                chunk=candidate.chunk,
                evidence=candidate.evidence,
            )
            for rank, (_, _, candidate) in enumerate(scored[:top_k], start=1)
        ]
