"""Graph summaries and symbol neighborhoods shared by the CLI and API."""

from repoagent.domain.errors import RetrievalError
from repoagent.graph.models import (
    EdgeType,
    GraphInspection,
    GraphSnapshot,
    GraphSummary,
)
from repoagent.graph.store import GraphStore


def graph_summary(snapshot: GraphSnapshot, repository: str) -> GraphSummary:
    node_counts: dict[str, int] = {}
    for node in snapshot.nodes:
        node_counts[node.node_type.value] = node_counts.get(node.node_type.value, 0) + 1
    edge_counts: dict[str, int] = {}
    for edge in snapshot.edges:
        edge_counts[edge.edge_type.value] = edge_counts.get(edge.edge_type.value, 0) + 1
    return GraphSummary(
        repository=repository,
        node_count=len(snapshot.nodes),
        edge_count=len(snapshot.edges),
        nodes_by_type=node_counts,
        edges_by_type=edge_counts,
    )


def graph_inspection(
    store: GraphStore, snapshot: GraphSnapshot, symbol: str
) -> GraphInspection:
    if not store.has_node(symbol):
        raise RetrievalError(f"Symbol not found in graph: {symbol}")
    structural = {EdgeType.CONTAINS, EdgeType.DEFINES}
    return GraphInspection(
        symbol=symbol,
        node=store.get_node(symbol),
        outgoing=store.outgoing(symbol),
        incoming=[
            edge for edge in store.incoming(symbol) if edge.edge_type not in structural
        ],
        parents=[
            edge for edge in store.incoming(symbol) if edge.edge_type in structural
        ],
    )
