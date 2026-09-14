"""Inspection reads the indexed snapshot, never arbitrary live repository files."""

from repoagent.graph.models import EdgeType, GraphInspection
from repoagent.graph.store import GraphStore
from repoagent.graph.traversal import TraversalConfig, traverse
from repoagent.retrieval.models import CodeChunk
from repoagent.tools.models import FileInput, FileInspection, NeighborReport

_STRUCTURAL = {EdgeType.CONTAINS, EdgeType.DEFINES}


class SnapshotInspection:
    def __init__(self, graph: GraphStore | None, chunks: list[CodeChunk]) -> None:
        self.graph, self.chunks = graph, chunks

    def symbol(self, name: str) -> GraphInspection:
        if self.graph is None or not self.graph.has_node(name):
            return GraphInspection(symbol=name)
        incoming = self.graph.incoming(name)
        return GraphInspection(
            symbol=name,
            node=self.graph.get_node(name),
            outgoing=self.graph.outgoing(name)[:20],
            incoming=[e for e in incoming if e.edge_type not in _STRUCTURAL][:20],
            parents=[e for e in incoming if e.edge_type in _STRUCTURAL][:20],
        )

    def neighbors(self, name: str, max_nodes: int) -> list[NeighborReport]:
        if self.graph is None or not self.graph.has_node(name):
            return []
        found = traverse(
            self.graph, [name], TraversalConfig(max_depth=1, max_nodes=max_nodes)
        )
        results = []
        for item in found:
            node = self.graph.get_node(item.node_id)
            if item.path and node:
                edge = item.path[0]
                results.append(
                    NeighborReport(
                        node_id=node.node_id,
                        node_type=node.node_type.value,
                        file_path=node.file_path,
                        relation=edge.edge_type.value,
                        resolved=edge.resolved,
                    )
                )
        return results

    def file(self, request: FileInput) -> FileInspection:
        chunks = [c for c in self.chunks if c.file_path == request.path]
        end = min(
            request.end_line or request.start_line + 399, request.start_line + 399
        )
        lines = {}
        for chunk in chunks:
            for number, line in enumerate(chunk.source.splitlines(), chunk.start_line):
                if request.start_line <= number <= end:
                    lines[number] = line
        if not lines:
            return FileInspection(
                path=request.path,
                start_line=request.start_line,
                end_line=request.start_line,
                content="",
                exists=False,
            )
        end = max(lines)
        content = "\n".join(
            lines.get(i, "") for i in range(request.start_line, end + 1)
        )
        return FileInspection(
            path=request.path,
            start_line=request.start_line,
            end_line=end,
            content=content[:4000],
        )
