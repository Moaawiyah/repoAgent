"""Named, configurable graph-expansion policies for hybrid+graph retrieval."""

from dataclasses import dataclass, field, replace

from repoagent.graph.models import EdgeType
from repoagent.graph.scoring import DEFAULT_EDGE_WEIGHTS, ScoringConfig
from repoagent.graph.traversal import TraversalConfig


@dataclass(frozen=True)
class GraphPolicy:
    """Everything that decides how selective graph expansion is.

    ``max_seeds`` bounds how many top hybrid results are expanded (None =
    all fused seeds). ``fusion_weight`` scales the graph ranking in
    weighted RRF; ``confident_weight`` replaces it when the top seed is
    ranked first by every contributing retriever, i.e. when lexical and
    semantic evidence already agree and expansion is mostly noise. An
    edge type with weight 0 is never traversed; ``unresolved_weight`` 0
    never traverses statically uncertain edges.
    """

    name: str = "legacy"
    max_depth: int = 2
    max_nodes: int = 32
    edge_weights: dict[EdgeType, float] = field(
        default_factory=lambda: dict(DEFAULT_EDGE_WEIGHTS)
    )
    unresolved_weight: float = 1.0
    max_seeds: int | None = None
    fusion_weight: float = 1.0
    confident_weight: float | None = None

    def traversal(self) -> TraversalConfig:
        allowed = frozenset(t for t, w in self.edge_weights.items() if w > 0)
        return TraversalConfig(
            max_depth=self.max_depth,
            max_nodes=self.max_nodes,
            allowed_edge_types=allowed,
            include_unresolved=self.unresolved_weight > 0,
        )

    def scoring(self) -> ScoringConfig:
        return ScoringConfig(
            weights=dict(self.edge_weights), unresolved_weight=self.unresolved_weight
        )


def _typed(overrides: dict[str, float]) -> dict[EdgeType, float]:
    return {EdgeType(key): value for key, value in overrides.items()}


def _weights(**overrides: float) -> dict[EdgeType, float]:
    return {**DEFAULT_EDGE_WEIGHTS, **_typed(overrides)}


# "legacy" reproduces the pre-policy behavior exactly, for ablations.
GRAPH_POLICIES: dict[str, GraphPolicy] = {
    "legacy": GraphPolicy(),
    "seeds5_gated": GraphPolicy(
        name="seeds5_gated", unresolved_weight=0.3, max_seeds=5, confident_weight=0.5
    ),
    "focused": GraphPolicy(
        name="focused",
        edge_weights=_weights(contains=0, defines=0, imports=0),
        unresolved_weight=0.3,
    ),
    "resolved_only": GraphPolicy(name="resolved_only", unresolved_weight=0.0),
    "seeds5": GraphPolicy(name="seeds5", max_seeds=5),
    "gated": GraphPolicy(name="gated", confident_weight=0.5),
    "calls_inherits": GraphPolicy(
        name="calls_inherits", edge_weights=_weights(contains=0, defines=0, imports=0)
    ),
    "depth1": GraphPolicy(name="depth1", max_depth=1),
    "half_weight": GraphPolicy(name="half_weight", fusion_weight=0.5),
}


# The preset used whenever no policy is configured (SearchService, settings).
DEFAULT_GRAPH_POLICY = "calls_inherits"


def graph_policy(
    name: str = DEFAULT_GRAPH_POLICY,
    edge_weights: dict[str, float] | None = None,
    unresolved_weight: float | None = None,
    max_depth: int | None = None,
) -> GraphPolicy:
    """Resolve a preset by name and apply explicit overrides on top."""
    if name not in GRAPH_POLICIES:
        raise ValueError(f"Unknown graph policy: {name}")
    policy = GRAPH_POLICIES[name]
    if edge_weights:
        weights = {**policy.edge_weights, **_typed(edge_weights)}
        policy = replace(policy, edge_weights=weights)
    if unresolved_weight is not None:
        policy = replace(policy, unresolved_weight=unresolved_weight)
    if max_depth is not None:
        policy = replace(policy, max_depth=max_depth)
    return policy
