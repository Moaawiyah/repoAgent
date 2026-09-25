"""Shared Reciprocal Rank Fusion used by every hybrid strategy."""

from repoagent.retrieval.models import CodeChunk, RetrievalResult, RetrievalSource


def rrf_fuse(
    ranked_lists: list[list[RetrievalResult]],
    rrf_k: int = 60,
    source: RetrievalSource = RetrievalSource.HYBRID,
    weights: list[float] | None = None,
) -> list[RetrievalResult]:
    """Fuse ranked result lists with Reciprocal Rank Fusion.

    RRF combines ranks instead of raw scores, so incompatible score
    scales are never mixed: ``score(d) = sum over lists of 1/(k + rank)``.
    A chunk appearing in several lists contributes once per list. Ties
    break by chunk identifier, keeping results deterministic. Evidence
    entries from the inputs are carried onto the fused results. Optional
    per-list ``weights`` scale each list's contribution (weighted RRF).
    """
    scores: dict[str, float] = {}
    chunks: dict[str, CodeChunk] = {}
    evidence: dict[str, list] = {}
    for index, results in enumerate(ranked_lists):
        weight = weights[index] if weights else 1.0
        for rank, result in enumerate(results, start=1):
            chunk_id = result.chunk.chunk_id
            scores[chunk_id] = scores.get(chunk_id, 0.0) + weight / (rrf_k + rank)
            chunks[chunk_id] = result.chunk
            evidence[chunk_id] = [*evidence.get(chunk_id, []), *result.evidence]
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return [
        RetrievalResult(
            rank=rank,
            score=score,
            source=source,
            chunk=chunks[chunk_id],
            evidence=evidence[chunk_id],
        )
        for rank, (chunk_id, score) in enumerate(ordered, start=1)
    ]
