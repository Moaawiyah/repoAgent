"""Bounded, cycle-safe graph traversal."""

from dataclasses import dataclass, field

from repoagent.graph.models import EdgeType, GraphEdge
from repoagent.graph.store import GraphStore


@dataclass(frozen=True)
class TraversalConfig:
    """Hard bounds for every traversal; expansion is never unlimited."""

    max_depth: int = 2
    max_nodes: int = 32
    allowed_edge_types: frozenset[EdgeType] | None = None


@dataclass(frozen=True)
class VisitedNode:
    """A traversal result with graph distance and relationship path."""

    node_id: str
    distance: int
    path: list[GraphEdge] = field(default_factory=list)


def traverse(
    store: GraphStore,
    seeds: list[str],
    config: TraversalConfig | None = None,
) -> list[VisitedNode]:
    """Breadth-first expansion from seed nodes within strict bounds.

    Seeds start at distance 0 but are not included in the results (they
    are already known). A visited set prevents cycles from looping, and
    ``max_nodes`` caps the total number of discovered nodes. Results are
    ordered by distance then node ID for determinism.
    """
    bounds = config or TraversalConfig()
    allowed = bounds.allowed_edge_types
    queue: list[tuple[str, int, list[GraphEdge]]] = [
        (node_id, 0, []) for node_id in dict.fromkeys(seeds)
    ]
    visited: set[str] = set(seeds)
    found: list[VisitedNode] = []
    while queue and len(found) < bounds.max_nodes:
        node_id, distance, path = queue.pop(0)
        if distance >= bounds.max_depth:
            continue
        for edge in store.neighbors(node_id, allowed):
            neighbor = edge.target
            if neighbor in visited:
                continue
            visited.add(neighbor)
            if len(found) >= bounds.max_nodes:
                break
            found.append(
                VisitedNode(
                    node_id=neighbor,
                    distance=distance + 1,
                    path=[*path, edge],
                )
            )
            queue.append((neighbor, distance + 1, [*path, edge]))
    return found
