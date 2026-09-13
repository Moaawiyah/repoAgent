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
from repoagent.ports.task_store import TaskStore
from repoagent.retrieval.models import (
    CodeChunk,
    IndexSummary,
    RetrievalResult,
    RetrievalSource,
    RetrievalStrategy,
    SearchRequest,
    SearchResponse,
)
from repoagent.sdk import RepoAgent

__version__ = "0.1.0"

__all__ = [
    "CodeChunk",
    "CodeSymbol",
    "EmbeddingProviderError",
    "FileAnalysis",
    "FileError",
    "ImportInfo",
    "ImportOrigin",
    "IndexNotFound",
    "IndexSummary",
    "InvalidTransition",
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
