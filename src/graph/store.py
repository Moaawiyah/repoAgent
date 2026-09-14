"""Graph store abstraction and the in-memory implementation."""

from typing import Protocol

from repoagent.graph.models import (
    EdgeType,
    GraphEdge,
    GraphNode,
    GraphSnapshot,
    NodeType,
)


class GraphStore(Protocol):
    """Query surface over a code knowledge graph."""

    def add_node(self, node: GraphNode) -> None: ...

    def add_edge(self, edge: GraphEdge) -> None: ...

    def get_node(self, node_id: str) -> GraphNode | None: ...

    def has_node(self, node_id: str) -> bool: ...

    def neighbors(
        self, node_id: str, edge_types: set[EdgeType] | None = None
    ) -> list[GraphEdge]: ...

    def incoming(
        self, node_id: str, edge_types: set[EdgeType] | None = None
    ) -> list[GraphEdge]: ...

    def outgoing(
        self, node_id: str, edge_types: set[EdgeType] | None = None
    ) -> list[GraphEdge]: ...

    def nodes_by_type(self, node_type: NodeType) -> list[GraphNode]: ...


class InMemoryGraphStore:
    """Deterministic in-memory graph with lookup indexes.

    Neighbor reads follow only edges whose endpoints exist, so dangling
    unresolved references are preserved on the edge list without ever
    producing phantom traversal targets. Duplicate edges collapse.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: dict[tuple[str, str, EdgeType], GraphEdge] = {}
        self._by_name: dict[str, list[str]] = {}
        self._by_file: dict[str, list[str]] = {}

    def add_node(self, node: GraphNode) -> None:
        self._nodes[node.node_id] = node
        self._by_name.setdefault(node.name, []).append(node.node_id)
        self._by_file.setdefault(node.file_path, []).append(node.node_id)

    def add_edge(self, edge: GraphEdge) -> None:
        key = (edge.source, edge.target, edge.edge_type)
        existing = self._edges.get(key)
        if existing is not None and existing.resolved:
            return
        self._edges[key] = edge

    def get_node(self, node_id: str) -> GraphNode | None:
        return self._nodes.get(node_id)

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    def _edges_touching(
        self, node_id: str, outgoing: bool, edge_types: set[EdgeType] | None
    ) -> list[GraphEdge]:
        edges = [
            edge
            for key, edge in self._edges.items()
            if (key[0] == node_id if outgoing else key[1] == node_id)
            if edge_types is None or edge.edge_type in edge_types
        ]
        return sorted(
            edges,
            key=lambda edge: (
                edge.edge_type.value,
                edge.source,
                edge.target,
                edge.line or 0,
            ),
        )

    def neighbors(
        self, node_id: str, edge_types: set[EdgeType] | None = None
    ) -> list[GraphEdge]:
        """Edges usable for traversal: existing endpoints only."""
        return [
            edge
            for edge in self.outgoing(node_id, edge_types)
            if edge.target in self._nodes
        ]

    def outgoing(
        self, node_id: str, edge_types: set[EdgeType] | None = None
    ) -> list[GraphEdge]:
        return self._edges_touching(node_id, True, edge_types)

    def incoming(
        self, node_id: str, edge_types: set[EdgeType] | None = None
    ) -> list[GraphEdge]:
        return self._edges_touching(node_id, False, edge_types)

    def nodes_by_type(self, node_type: NodeType) -> list[GraphNode]:
        return sorted(
            (node for node in self._nodes.values() if node.node_type is node_type),
            key=lambda node: node.node_id,
        )

    def node_ids(self) -> set[str]:
        return set(self._nodes)

    def nodes_by_simple_name(self, name: str) -> list[str]:
        return sorted(self._by_name.get(name, []))

    def to_snapshot(self) -> GraphSnapshot:
        return GraphSnapshot(
            nodes=sorted(self._nodes.values(), key=lambda node: node.node_id),
            edges=sorted(
                self._edges.values(),
                key=lambda e: (e.edge_type.value, e.source, e.target),
            ),
        )


def store_from_snapshot(snapshot: GraphSnapshot) -> InMemoryGraphStore:
    """Rebuild a queryable store from a persisted snapshot."""
    store = InMemoryGraphStore()
    for node in snapshot.nodes:
        store.add_node(node)
    for edge in snapshot.edges:
        store.add_edge(edge)
    return store
