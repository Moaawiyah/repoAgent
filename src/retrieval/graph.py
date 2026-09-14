"""Hybrid + graph retrieval: RRF seeds, bounded expansion, RRF fusion."""

from repoagent.graph.expansion import GraphExpander
from repoagent.retrieval.fusion import rrf_fuse
from repoagent.retrieval.models import (
    Evidence,
    RetrievalResult,
    RetrievalSource,
    RetrievalStrategy,
)
from repoagent.retrieval.retrievers import Retriever


class HybridGraphRetriever:
    """Extends the M3 hybrid pipeline with graph expansion.

    The hybrid (BM25+vector RRF) ranking provides seed symbols; the graph
    expander derives related candidates along static relationships; the
    two rankings are fused again with the same RRF implementation, so no
    fusion logic is duplicated. Evidence distinguishes lexical, vector,
    and graph contributions per result.
    """

    def __init__(
        self,
        hybrid: Retriever,
        expander: GraphExpander,
        rrf_k: int = 60,
    ) -> None:
        self._hybrid = hybrid
        self._expander = expander
        self._rrf_k = rrf_k

    def search(self, query: str, top_k: int) -> list[RetrievalResult]:
        depth = max(top_k * 2, 10)
        seeds = self._hybrid.search(query, depth)
        graph_results = self._expander.expand(seeds, depth)
        fused = rrf_fuse(
            [seeds, graph_results],
            self._rrf_k,
            source=RetrievalSource.HYBRID_GRAPH,
        )
        return [
            self._annotated(result, seeds, graph_results) for result in fused[:top_k]
        ]

    @staticmethod
    def _annotated(
        result: RetrievalResult,
        seeds: list[RetrievalResult],
        graph_results: list[RetrievalResult],
    ) -> RetrievalResult:
        """Record seed rank and graph distance/path in the evidence."""
        evidence = list(result.evidence)
        for rank, seed in enumerate(seeds, start=1):
            if seed.chunk.chunk_id == result.chunk.chunk_id:
                evidence.append(Evidence(kind="hybrid_seed", rank=rank))
                break
        for graph_result in graph_results:
            if graph_result.chunk.chunk_id == result.chunk.chunk_id:
                evidence.extend(
                    Evidence(
                        kind="graph",
                        distance=note.distance,
                        path=note.path,
                    )
                    for note in graph_result.evidence
                    if note.kind == "graph"
                )
                break
        return result.model_copy(update={"evidence": evidence})


def build_graph_retriever(
    strategy: RetrievalStrategy,
    hybrid: Retriever,
    expander: GraphExpander | None,
) -> Retriever:
    """Select the retriever for hybrid strategies, enforcing graph data."""
    if strategy is RetrievalStrategy.HYBRID_GRAPH:
        if expander is None:
            from repoagent.domain.errors import RetrievalError

            raise RetrievalError("Index has no repository graph; rebuild the index")
        return HybridGraphRetriever(hybrid, expander)
    return hybrid
