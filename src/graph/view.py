"""Bounded, frontend-oriented projection of the native repository graph.

Only what the web graph needs is exposed: node identity/kind/location and
typed edges. Large graphs are truncated deterministically, keeping nodes
relevant to the task result first, then modules, classes, functions and
methods. No second graph model is introduced; nodes and edges are the M4
``GraphNode``/``GraphEdge`` values.
"""

from pydantic import Field

from repoagent.analysis.models import AnalysisModel
from repoagent.graph.models import GraphEdge, GraphSnapshot, NodeType

MAX_VIEW_NODES = 600
_KIND_ORDER = {
    NodeType.MODULE: 1,
    NodeType.CLASS: 2,
    NodeType.FUNCTION: 3,
    NodeType.METHOD: 4,
}


class ViewNode(AnalysisModel):
    id: str
    kind: NodeType
    name: str
    file: str
    start_line: int
    end_line: int
    parent: str | None = None
    module: str
    focus: bool = False


class GraphView(AnalysisModel):
    repository: str
    nodes: list[ViewNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    total_nodes: int = 0
    total_edges: int = 0
    truncated: bool = False


def build_view(
    snapshot: GraphSnapshot,
    repository: str,
    focus: set[str] | None = None,
    max_nodes: int = MAX_VIEW_NODES,
) -> GraphView:
    """``focus`` holds node ids or file paths referenced by the task result."""
    focus = focus or set()

    def focused(node) -> bool:
        return node.node_id in focus or node.file_path in focus

    ranked = sorted(
        snapshot.nodes,
        key=lambda n: (0 if focused(n) else _KIND_ORDER[n.node_type], n.node_id),
    )
    kept = ranked[:max_nodes]
    ids = {node.node_id for node in kept}
    edges = [e for e in snapshot.edges if e.source in ids and e.target in ids]
    nodes = [
        ViewNode(
            id=n.node_id,
            kind=n.node_type,
            name=n.name,
            file=n.file_path,
            start_line=n.start_line,
            end_line=n.end_line,
            parent=n.parent,
            module=n.module,
            focus=focused(n),
        )
        for n in sorted(kept, key=lambda n: n.node_id)
    ]
    return GraphView(
        repository=repository,
        nodes=nodes,
        edges=edges,
        total_nodes=len(snapshot.nodes),
        total_edges=len(snapshot.edges),
        truncated=len(kept) < len(snapshot.nodes),
    )
