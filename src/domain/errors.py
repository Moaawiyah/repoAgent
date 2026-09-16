"""Errors safe to present at application boundaries."""


class RepoAgentError(Exception):
    """An operational application failure."""


class TaskNotFound(RepoAgentError):
    """No task has the requested identifier."""


class InvalidTransition(RepoAgentError):
    """The requested lifecycle transition is disallowed."""


class UnsupportedSchema(RepoAgentError):
    """The database requires a different application schema."""


class StorageError(RepoAgentError):
    """Storage or filesystem access failed at the public SDK boundary."""


class RepositoryInvalid(RepoAgentError):
    """The repository exists but cannot be read as a source tree."""


class RetrievalError(RepoAgentError):
    """An indexing or retrieval operation failed."""


class IndexNotFound(RetrievalError):
    """No index exists for the requested repository."""


class EmbeddingProviderError(RetrievalError):
    """Embedding generation or an embedding-provider mismatch occurred."""


class ExportError(RepoAgentError):
    """A graph export could not be written safely."""


class GraphError(RepoAgentError):
    """A persisted graph document is missing, malformed, or incompatible."""


class LLMError(RepoAgentError):
    """A language-model provider is unavailable or misconfigured."""


class LLMOutputError(LLMError):
    """A provider returned output that failed structured validation."""


class InvestigationError(RepoAgentError):
    """An investigation could not be started or executed."""


class SandboxError(RepoAgentError):
    """The sandbox could not be created, executed, or cleaned up safely."""


class UnsafeCommandError(SandboxError):
    """A command or dependency specification violated the execution policy."""


class WorkspaceError(SandboxError):
    """A disposable workspace could not be prepared or patched safely."""
