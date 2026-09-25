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

    Each seed (from BM25/vector/hybrid retrieval) starts from its exact
    graph node (``chunk.node_id``), and every visited node maps back to
    its exact chunk via ``node.chunk_id``, so symbols sharing a qualified
    name stay distinct. Candidates are scored by seed rank, graph
    distance, and relationship weight; provenance keeps the full path.
    """

    def __init__(
        self,
        store: GraphStore,
        chunks: list[CodeChunk],
        traversal: TraversalConfig | None = None,
        scoring: ScoringConfig | None = None,
    ) -> None:
        self._store = store
        self._by_id = {chunk.chunk_id: chunk for chunk in chunks}
        # Fallback for indexes persisted before nodes carried chunk IDs.
        self._by_node = {
            chunk.node_id or chunk.qualified_name: chunk for chunk in chunks
        }
        self._traversal = traversal or TraversalConfig()
        self._scoring = scoring or ScoringConfig()

    def expand(self, seeds: list[RetrievalResult], top_k: int) -> list[RetrievalResult]:
        """Return graph-derived candidates ranked by deterministic score."""
        scored: dict[str, tuple[float, RetrievalResult]] = {}
        for seed in seeds:
            node = self._store.get_node(seed.chunk.node_id or seed.chunk.qualified_name)
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

    def _chunk_for(self, node_id: str) -> CodeChunk | None:
        node = self._store.get_node(node_id)
        if node is not None and node.chunk_id in self._by_id:
            return self._by_id[node.chunk_id]
        return self._by_node.get(node_id)

    def _candidate(self, seed: RetrievalResult, visited) -> RetrievalResult | None:
        chunk = self._chunk_for(visited.node_id)
        if chunk is None:
            return None
        edge_types = [edge.edge_type for edge in visited.path]
        uncertain = sum(not edge.resolved for edge in visited.path)
        score = self._scoring.score(seed.rank, visited.distance, edge_types, uncertain)
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
