"""Persistent ``graph.json`` interchange format for the repository graph.

``GraphDocument`` wraps the same ``GraphSnapshot`` used by retrieval and the
Obsidian exporter with repository identity, schema/version metadata, and
summary counts, so a graph can be written once and reloaded later without
re-running static analysis.
"""

import json
from pathlib import Path

from pydantic import Field

from repoagent.analysis.models import AnalysisModel
from repoagent.domain.errors import GraphError
from repoagent.graph.models import GraphEdge, GraphNode, GraphSnapshot

GRAPH_SCHEMA_VERSION = "1.0"


class GraphMetadata(AnalysisModel):
    """Summary counts describing the analyzed repository."""

    files: int
    symbols: int
    relationships: int


class GraphDocument(AnalysisModel):
    """Deterministic, versioned ``graph.json`` contents."""

    schema_version: str = GRAPH_SCHEMA_VERSION
    repository: str
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    metadata: GraphMetadata


class GraphifyResult(AnalysisModel):
    """Typed result of running the Graphify pipeline end to end."""

    repository: str
    files: int
    symbols: int
    node_count: int
    edge_count: int
    graph_json_path: str | None = None
    obsidian_path: str | None = None


def build_document(
    snapshot: GraphSnapshot, *, repository: str, files: int, symbols: int
) -> GraphDocument:
    """Wrap a graph snapshot with repository identity and summary counts."""
    return GraphDocument(
        repository=repository,
        nodes=snapshot.nodes,
        edges=snapshot.edges,
        metadata=GraphMetadata(
            files=files, symbols=symbols, relationships=len(snapshot.edges)
        ),
    )


def document_to_snapshot(document: GraphDocument) -> GraphSnapshot:
    """Recover the plain graph snapshot from a persisted document."""
    return GraphSnapshot(nodes=document.nodes, edges=document.edges)


def write_graph_json(document: GraphDocument, path: Path) -> None:
    """Write a deterministic, indented ``graph.json`` file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(document.model_dump(mode="json"), indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
    except OSError as error:
        raise GraphError(f"Could not write graph.json to {path}") from error


def read_graph_json(path: Path) -> GraphDocument:
    """Load a previously written ``graph.json`` without re-analyzing."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise GraphError(f"Could not read graph.json from {path}") from error
    except json.JSONDecodeError as error:
        raise GraphError(f"graph.json at {path} is not valid JSON") from error
    if raw.get("schema_version") != GRAPH_SCHEMA_VERSION:
        raise GraphError(
            f"Unsupported graph.json schema version: {raw.get('schema_version')!r}"
        )
    try:
        return GraphDocument.model_validate(raw)
    except ValueError as error:
        raise GraphError(f"graph.json at {path} failed validation") from error
