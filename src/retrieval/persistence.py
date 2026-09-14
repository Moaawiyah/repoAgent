"""Persisted retrieval index models."""

from pydantic import Field

from repoagent.analysis.models import AnalysisModel
from repoagent.graph.models import GraphSnapshot
from repoagent.retrieval.models import CodeChunk


class IndexSnapshot(AnalysisModel):
    """Persisted retrieval index for one repository, graph included."""

    repo_id: str
    repository_root: str
    embedding_provider: str
    embedding_dimension: int
    chunks: list[CodeChunk]
    vectors: dict[str, list[float]] = Field(default_factory=dict)
    graph: GraphSnapshot | None = None


class IndexSummary(AnalysisModel):
    """Typed result of an indexing operation."""

    repository_name: str
    repository_id: str
    repository_root: str
    python_files: int
    chunk_count: int
    embedding_provider: str
    embedding_dimension: int
    node_count: int = 0
    edge_count: int = 0
