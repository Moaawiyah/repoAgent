"""Indexing workflow: analysis, chunking, embedding, persistence."""

import logging
from pathlib import Path

from repoagent.analysis.analyzer import RepositoryAnalyzer
from repoagent.domain.errors import EmbeddingProviderError
from repoagent.domain.repository import RepositorySpec
from repoagent.ports.index_store import IndexStore
from repoagent.retrieval.chunking import CodeChunker
from repoagent.retrieval.embeddings import EmbeddingProvider
from repoagent.retrieval.models import (
    CodeChunk,
    IndexSnapshot,
    IndexSummary,
    repository_identifier,
)


class IndexService:
    """Builds and persists a retrieval index for one repository."""

    def __init__(
        self,
        store: IndexStore,
        provider: EmbeddingProvider,
        analyzer: RepositoryAnalyzer | None = None,
    ) -> None:
        self._store = store
        self._provider = provider
        self._analyzer = analyzer or RepositoryAnalyzer()

    def index(self, spec: RepositorySpec) -> IndexSummary:
        """Analyze, chunk, embed once, and persist the index snapshot."""
        logging.getLogger(__name__).info(
            "Repository indexing started", extra={"event": "index_started"}
        )
        analysis = self._analyzer.analyze(spec)
        repo_id = repository_identifier(analysis.repository_root)
        chunks = CodeChunker(repo_id).chunk(analysis, Path(analysis.repository_root))
        logging.getLogger(__name__).info(
            "Chunks generated", extra={"event": "chunks_generated"}
        )
        snapshot = IndexSnapshot(
            repo_id=repo_id,
            repository_root=analysis.repository_root,
            embedding_provider=self._provider.name,
            embedding_dimension=self._provider.dimension,
            chunks=chunks,
            vectors=self._embed(chunks),
        )
        self._store.save(snapshot)
        logging.getLogger(__name__).info(
            "Index stored", extra={"event": "index_stored"}
        )
        return IndexSummary(
            repository_name=analysis.repository_name,
            repository_id=repo_id,
            repository_root=analysis.repository_root,
            python_files=analysis.python_files,
            chunk_count=len(chunks),
            embedding_provider=self._provider.name,
            embedding_dimension=self._provider.dimension,
        )

    def _embed(self, chunks: list[CodeChunk]) -> dict[str, list[float]]:
        """Embed every chunk exactly once in a single batch."""
        if not chunks:
            return {}
        try:
            vectors = self._provider.embed([chunk.search_text for chunk in chunks])
        except Exception as error:
            raise EmbeddingProviderError("Embedding generation failed") from error
        return {
            chunk.chunk_id: vector
            for chunk, vector in zip(chunks, vectors, strict=True)
        }
