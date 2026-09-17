"""Detects circular module-import dependencies from the repository graph.

Standard white/gray/black DFS over resolved `IMPORTS` edges between module
nodes: a back-edge to a gray (in-progress) ancestor is a cycle. This finds
one representative cycle per back-edge in O(V+E), not every simple cycle in
the graph, which keeps the check bounded on dense repositories.
"""

from repoagent.audit.context import AuditContext
from repoagent.domain.audit import (
    CandidateIssue,
    DetectionSource,
    IssueCategory,
    Severity,
    stable_candidate_id,
)
from repoagent.graph.models import EdgeType, NodeType
from repoagent.graph.store import GraphStore

MAX_CYCLES = 20


def _module_graph(graph: GraphStore) -> dict[str, list[str]]:
    modules = {node.node_id for node in graph.nodes_by_type(NodeType.MODULE)}
    adjacency = {}
    for module_id in modules:
        targets = {
            edge.target
            for edge in graph.outgoing(module_id, {EdgeType.IMPORTS})
            if edge.resolved and edge.target in modules and edge.target != module_id
        }
        adjacency[module_id] = sorted(targets)
    return adjacency


def _file_path(graph: GraphStore, module_id: str) -> str:
    node = graph.get_node(module_id)
    return node.file_path if node is not None else module_id


def _canonical(cycle: list[str]) -> tuple[str, ...]:
    start = cycle.index(min(cycle))
    return tuple(cycle[start:] + cycle[:start])


def find_cycles(adjacency: dict[str, list[str]]) -> list[list[str]]:
    color: dict[str, int] = {}
    path: list[str] = []
    found: dict[tuple[str, ...], list[str]] = {}

    def visit(node: str) -> None:
        color[node] = 1
        path.append(node)
        for neighbor in adjacency.get(node, []):
            if len(found) >= MAX_CYCLES:
                break
            if color.get(neighbor, 0) == 1:
                index = path.index(neighbor)
                cycle = [*path[index:], neighbor]
                found.setdefault(_canonical(cycle[:-1]), cycle)
            elif color.get(neighbor, 0) == 0:
                visit(neighbor)
        path.pop()
        color[node] = 2

    for node in sorted(adjacency):
        if color.get(node, 0) == 0 and len(found) < MAX_CYCLES:
            visit(node)
    return sorted(found.values(), key=lambda cycle: cycle[0])


class CircularDependencyDetector:
    """Flags circular module imports found in the code knowledge graph."""

    name = "circular_dependency"

    def detect(self, context: AuditContext) -> list[CandidateIssue]:
        cycles = find_cycles(_module_graph(context.graph))
        return [self._candidate(context.graph, cycle) for cycle in cycles]

    @staticmethod
    def _candidate(graph: GraphStore, cycle: list[str]) -> CandidateIssue:
        files = [_file_path(graph, module_id) for module_id in cycle]
        path = " -> ".join([*files, files[0]])
        severity = Severity.HIGH if len(cycle) == 2 else Severity.MEDIUM
        return CandidateIssue(
            id=stable_candidate_id(
                IssueCategory.CIRCULAR_DEPENDENCY, files[0], 1, path
            ),
            category=IssueCategory.CIRCULAR_DEPENDENCY,
            title="Circular module dependency",
            description=f"Modules import each other in a cycle: {path}",
            confidence=0.9,
            severity=severity,
            file=files[0],
            symbol=cycle[0],
            start_line=1,
            end_line=1,
            detection_source=DetectionSource.GRAPH_CIRCULAR_DEPENDENCY,
        )
