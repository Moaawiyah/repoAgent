"""Graph expansion of retrieval seeds into ranked graph candidates."""

from repoagent.graph.scoring import ScoringConfig
from repoagent.graph.store import GraphStore
from repoagent.graph.traversal import TraversalConfig, traverse
from repoagent.retrieval.models import (
    CodeChunk,
    Evidence,
    GraphHop,
    RetrievalResult,
    RetrievalSource,
)


class GraphExpander:
    """Expands strong seed results along graph relationships.

    Seeds (from BM25/vector/hybrid retrieval) are mapped to graph nodes
    via their qualified names, traversed within bounds, and scored by
    seed rank, graph distance, and relationship weight. Provenance keeps
    the full relationship path for each candidate.
    """

    def __init__(
        self,
        store: GraphStore,
        chunks_by_qualified: dict[str, CodeChunk],
        traversal: TraversalConfig | None = None,
        scoring: ScoringConfig | None = None,
    ) -> None:
        self._store = store
        self._chunks = chunks_by_qualified
        self._traversal = traversal or TraversalConfig()
        self._scoring = scoring or ScoringConfig()

    def expand(self, seeds: list[RetrievalResult], top_k: int) -> list[RetrievalResult]:
        """Return graph-derived candidates ranked by deterministic score."""
        scored: dict[str, tuple[float, RetrievalResult]] = {}
        for seed in seeds:
            node = self._store.get_node(seed.chunk.qualified_name)
            if node is None:
                continue
            for visited in traverse(self._store, [node.node_id], self._traversal):
                result = self._candidate(seed, visited)
                if result is None:
                    continue
                previous = scored.get(visited.node_id)
                if previous is None or result.score > previous[0]:
                    scored[visited.node_id] = (result.score, result)
        ranked = sorted(
            scored.values(), key=lambda item: (-item[0], item[1].chunk.chunk_id)
        )
        return [
            result.model_copy(update={"rank": position})
            for position, (_, result) in enumerate(ranked[:top_k], start=1)
        ]

    def _candidate(self, seed: RetrievalResult, visited) -> RetrievalResult | None:
        chunk = self._chunks.get(visited.node_id)
        if chunk is None:
            return None
        edge_types = [edge.edge_type for edge in visited.path]
        score = self._scoring.score(seed.rank, visited.distance, edge_types)
        if score <= 0.0:
            return None
        hops = [
            GraphHop(
                source_symbol=edge.source,
                relation=edge.edge_type.value,
                target_symbol=edge.target,
            )
            for edge in visited.path
        ]
        evidence = Evidence(
            kind="graph",
            distance=visited.distance,
            path=hops,
        )
        return RetrievalResult(
            rank=0,
            score=score,
            source=RetrievalSource.GRAPH,
            chunk=chunk,
            evidence=[*seed.evidence, evidence],
        )
