"""Typed models for chunking, retrieval, evaluation, and index persistence."""

import hashlib
from enum import StrEnum
from pathlib import Path

from pydantic import Field, field_validator

from repoagent.analysis.models import AnalysisModel, SymbolType


class RetrievalSource(StrEnum):
    """Which retriever produced a result."""

    BM25 = "bm25"
    VECTOR = "vector"
    HYBRID = "hybrid"


class RetrievalStrategy(StrEnum):
    """Configurable search strategy."""

    BM25 = "bm25"
    VECTOR = "vector"
    HYBRID = "hybrid"


class CodeChunk(AnalysisModel):
    """A structure-aware, addressable unit of retrieved code."""

    chunk_id: str
    repository_id: str
    file_path: str
    language: str
    symbol_name: str
    qualified_name: str
    symbol_type: SymbolType
    start_line: int
    end_line: int
    source: str
    parent: str | None = None
    docstring: str | None = None
    imports: list[str] = Field(default_factory=list)

    @property
    def search_text(self) -> str:
        """Searchable representation: path, names, docstring, and source."""
        parts = [self.file_path, self.qualified_name, self.symbol_name]
        if self.docstring:
            parts.append(self.docstring)
        parts.append(self.source)
        return "\n".join(parts)


class RetrievalResult(AnalysisModel):
    """A scored retrieval hit preserving full provenance."""

    rank: int
    score: float
    source: RetrievalSource
    chunk: CodeChunk


class SearchRequest(AnalysisModel):
    """Validated search input."""

    repository: str
    query: str
    strategy: RetrievalStrategy = RetrievalStrategy.HYBRID
    top_k: int = Field(default=5, ge=1, le=100)
    rerank: bool = False

    @field_validator("query")
    @classmethod
    def _clean_query(cls, value: str) -> str:
        query = value.strip()
        if not query:
            raise ValueError("A nonempty query is required")
        return query


class SearchResponse(AnalysisModel):
    """A complete, provenance-preserving search outcome."""

    repository: str
    repository_id: str
    query: str
    strategy: RetrievalStrategy
    reranked: bool
    results: list[RetrievalResult]


class IndexSnapshot(AnalysisModel):
    """Persisted retrieval index for one repository."""

    repo_id: str
    repository_root: str
    embedding_provider: str
    embedding_dimension: int
    chunks: list[CodeChunk]
    vectors: dict[str, list[float]] = Field(default_factory=dict)


class IndexSummary(AnalysisModel):
    """Typed result of an indexing operation."""

    repository_name: str
    repository_id: str
    repository_root: str
    python_files: int
    chunk_count: int
    embedding_provider: str
    embedding_dimension: int


def repository_identifier(root: str) -> str:
    """Deterministic, collision-resistant repository identity."""
    resolved = str(Path(root).resolve())
    digest = hashlib.sha256(resolved.encode()).hexdigest()[:8]
    return f"{Path(resolved).name}-{digest}"


def make_chunk_id(
    repository_id: str, file_path: str, qualified_name: str, source: str
) -> str:
    """Stable chunk identity: repository + file + symbol + source hash."""
    source_hash = hashlib.sha256(source.encode()).hexdigest()
    key = f"{repository_id}|{file_path}|{qualified_name}|{source_hash}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]
