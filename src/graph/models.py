"""Typed code knowledge graph models with deterministic identities."""

from enum import StrEnum

from pydantic import Field

from repoagent.analysis.models import AnalysisModel


class NodeType(StrEnum):
    """Kinds of graph nodes derived from static analysis."""

    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"


class EdgeType(StrEnum):
    """Static relationship types; CALLS is conservatively resolved."""

    DEFINES = "defines"
    CONTAINS = "contains"
    IMPORTS = "imports"
    INHERITS = "inherits"
    CALLS = "calls"


class GraphNode(AnalysisModel):
    """A graph node; identity is the stable qualified name."""

    node_id: str
    node_type: NodeType
    name: str
    file_path: str
    start_line: int
    end_line: int
    parent: str | None = None
    module: str
    chunk_id: str | None = None


class GraphEdge(AnalysisModel):
    """A directed, typed relationship; ``resolved=False`` marks ambiguity."""

    source: str
    target: str
    edge_type: EdgeType
    line: int | None = None
    resolved: bool = True


class GraphSnapshot(AnalysisModel):
    """Serializable, deterministic graph interchange form."""

    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class GraphSummary(AnalysisModel):
    """Aggregate counts for graph presentation."""

    repository: str
    node_count: int
    edge_count: int
    nodes_by_type: dict[str, int]
    edges_by_type: dict[str, int]


class GraphInspection(AnalysisModel):
    """Neighborhood view of one symbol for inspection output."""

    symbol: str
    node: GraphNode | None = None
    outgoing: list[GraphEdge] = Field(default_factory=list)
    incoming: list[GraphEdge] = Field(default_factory=list)
    parents: list[GraphEdge] = Field(default_factory=list)
