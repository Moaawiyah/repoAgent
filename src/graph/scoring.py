"""Deterministic scoring for graph-derived retrieval candidates."""

from dataclasses import dataclass, field

from repoagent.graph.models import EdgeType

DEFAULT_EDGE_WEIGHTS: dict[EdgeType, float] = {
    EdgeType.CALLS: 1.0,
    EdgeType.INHERITS: 0.9,
    EdgeType.CONTAINS: 0.8,
    EdgeType.DEFINES: 0.7,
    EdgeType.IMPORTS: 0.5,
}


@dataclass(frozen=True)
class ScoringConfig:
    """Distance decay and per-relationship weights.

    Closer nodes and stronger relationships rank higher; the seed rank
    keeps the initial retrieval evidence in the score so a strong lexical
    seed outweighs a distant graph-only path. Each statically uncertain
    hop (``resolved=False``) multiplies the score by ``unresolved_weight``.
    """

    decay: float = 0.6
    weights: dict[EdgeType, float] = field(
        default_factory=lambda: dict(DEFAULT_EDGE_WEIGHTS)
    )
    unresolved_weight: float = 1.0

    def score(
        self,
        seed_rank: int,
        distance: int,
        edge_types: list[EdgeType],
        unresolved_hops: int = 0,
    ) -> float:
        """Combine seed rank, distance decay, and relationship weights."""
        if seed_rank < 1 or distance < 1:
            return 0.0
        seed_weight = 1.0 / seed_rank
        decayed = self.decay ** (distance - 1)
        weight = min(
            (self.weights.get(edge_type, 0.5) for edge_type in edge_types),
            default=0.5,
        )
        uncertainty = self.unresolved_weight**unresolved_hops
        return seed_weight * decayed * weight * uncertainty
