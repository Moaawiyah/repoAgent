"""RepoAgent public Python SDK and typed contracts."""

from repoagent.analysis.models import (
    CodeSymbol,
    ImportInfo,
    ImportOrigin,
    RelationKind,
    Relationship,
    SymbolType,
)
from repoagent.analysis.results import FileAnalysis, FileError, RepositoryAnalysis
from repoagent.config import Settings
from repoagent.domain.errors import (
    EmbeddingProviderError,
    IndexNotFound,
    InvalidTransition,
    RepoAgentError,
    RepositoryInvalid,
    RetrievalError,
    StorageError,
    TaskNotFound,
    UnsupportedSchema,
)
from repoagent.domain.repository import RepositorySpec
from repoagent.domain.tasks import (
    TaskEvent,
    TaskKind,
    TaskRecord,
    TaskRequest,
    TaskStatus,
)
from repoagent.export.obsidian import ExportSummary
from repoagent.graph.models import (
    EdgeType,
    GraphEdge,
    GraphNode,
    GraphSnapshot,
    NodeType,
)
from repoagent.ports.task_store import TaskStore
from repoagent.retrieval.models import (
    CodeChunk,
    RetrievalResult,
    RetrievalSource,
    RetrievalStrategy,
    SearchRequest,
    SearchResponse,
)
from repoagent.retrieval.persistence import IndexSummary
from repoagent.sdk import RepoAgent

__version__ = "0.1.0"

__all__ = [
    "CodeChunk",
    "CodeSymbol",
    "EdgeType",
    "EmbeddingProviderError",
    "ExportSummary",
    "FileAnalysis",
    "FileError",
    "GraphEdge",
    "GraphNode",
    "GraphSnapshot",
    "ImportInfo",
    "ImportOrigin",
    "IndexNotFound",
    "IndexSummary",
    "InvalidTransition",
    "NodeType",
    "RelationKind",
    "Relationship",
    "RepoAgent",
    "RepoAgentError",
    "RepositoryAnalysis",
    "RepositoryInvalid",
    "RepositorySpec",
    "RetrievalError",
    "RetrievalResult",
    "RetrievalSource",
    "RetrievalStrategy",
    "SearchRequest",
    "SearchResponse",
    "Settings",
    "StorageError",
    "SymbolType",
    "TaskEvent",
    "TaskKind",
    "TaskNotFound",
    "TaskRecord",
    "TaskRequest",
    "TaskStatus",
    "TaskStore",
    "UnsupportedSchema",
]
