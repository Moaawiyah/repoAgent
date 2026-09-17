"""Detects excessive structural coupling from graph fan-in/fan-out counts.

Deterministic threshold over CALLS/IMPORTS edges already in the repository
graph; no new graph construction. Bounded to the worst offenders so it
cannot flood a large repository with low-value warnings.
"""

from repoagent.audit.context import AuditContext
from repoagent.domain.audit import (
    CandidateIssue,
    DetectionSource,
    IssueCategory,
    Severity,
    stable_candidate_id,
)
from repoagent.graph.models import EdgeType, GraphNode, NodeType
from repoagent.graph.store import GraphStore

_EDGE_TYPES = {EdgeType.CALLS, EdgeType.IMPORTS}
FAN_THRESHOLD = 15
HIGH_THRESHOLD = 30
MAX_REPORTED = 5


def _fan(graph: GraphStore, node_id: str) -> tuple[int, int]:
    fan_in = len(graph.incoming(node_id, _EDGE_TYPES))
    fan_out = len(graph.outgoing(node_id, _EDGE_TYPES))
    return fan_in, fan_out


class CouplingDetector:
    """Flags symbols/modules whose combined fan-in/out is excessive."""

    name = "coupling"

    def detect(self, context: AuditContext) -> list[CandidateIssue]:
        graph = context.graph
        scored = []
        node_ids = {
            node.node_id
            for node_type in NodeType
            for node in graph.nodes_by_type(node_type)
        }
        for node_id in node_ids:
            fan_in, fan_out = _fan(graph, node_id)
            total = fan_in + fan_out
            if total >= FAN_THRESHOLD:
                scored.append((total, node_id, fan_in, fan_out))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [
            self._candidate(graph, node_id, fan_in, fan_out)
            for _, node_id, fan_in, fan_out in scored[:MAX_REPORTED]
        ]

    @staticmethod
    def _candidate(
        graph: GraphStore, node_id: str, fan_in: int, fan_out: int
    ) -> CandidateIssue:
        gnode: GraphNode | None = graph.get_node(node_id)
        file_path = gnode.file_path if gnode else node_id
        line = gnode.start_line if gnode else 1
        total = fan_in + fan_out
        severity = Severity.HIGH if total >= HIGH_THRESHOLD else Severity.MEDIUM
        return CandidateIssue(
            id=stable_candidate_id(IssueCategory.COUPLING, file_path, line, node_id),
            category=IssueCategory.COUPLING,
            title="Excessive structural coupling",
            description=(
                f"`{node_id}` has fan-in {fan_in} and fan-out {fan_out} "
                f"(total {total}) across calls/imports, well above typical."
            ),
            confidence=0.7,
            severity=severity,
            file=file_path,
            symbol=node_id,
            start_line=line,
            end_line=line,
            detection_source=DetectionSource.GRAPH_COUPLING,
        )
