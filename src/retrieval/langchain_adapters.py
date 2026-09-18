"""LangChain-facing adapters around RepoAgent's own retrieval stack.

Nothing here replaces RepoAgent retrieval: ``RepoAgentRetriever`` exposes
the existing BM25 + vector + native-graph fusion (``SearchService``) as a
LangChain retriever/tool with full provenance metadata, and the embedding
adapters convert between RepoAgent's ``EmbeddingProvider`` protocol and
LangChain's ``Embeddings`` interface in both directions.
"""

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever
from langchain_core.tools import BaseTool, create_retriever_tool
from pydantic import Field

from repoagent.application.searching import SearchService
from repoagent.retrieval.embeddings import EmbeddingProvider
from repoagent.retrieval.models import RetrievalResult, RetrievalStrategy, SearchRequest


def to_document(result: RetrievalResult) -> Document:
    chunk = result.chunk
    distances = [e.distance for e in result.evidence if e.distance is not None]
    return Document(
        page_content=chunk.source,
        metadata={
            "chunk_id": chunk.chunk_id,
            "file_path": chunk.file_path,
            "qualified_name": chunk.qualified_name,
            "symbol_type": chunk.symbol_type.value,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "rank": result.rank,
            "score": result.score,
            "retrieval_source": result.source.value,
            "evidence": sorted({e.kind for e in result.evidence}),
            "graph_distance": min(distances) if distances else None,
        },
    )


class RepoAgentRetriever(BaseRetriever):
    """LangChain retriever over RepoAgent's hybrid/graph search."""

    search_service: SearchService
    repository: str
    strategy: RetrievalStrategy = RetrievalStrategy.HYBRID_GRAPH
    top_k: int = Field(default=5, ge=1, le=20)

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        request = SearchRequest(
            repository=self.repository,
            query=query,
            strategy=self.strategy,
            top_k=self.top_k,
        )
        return [to_document(r) for r in self.search_service.search(request).results]


def search_code_tool(retriever: RepoAgentRetriever) -> BaseTool:
    """Read-only LangChain tool for LangGraph nodes; no execution capability."""
    return create_retriever_tool(
        retriever,
        "search_code",
        "Search the indexed repository (BM25 + vector + code graph) and return "
        "source snippets with file and line provenance.",
    )


class LangChainEmbeddings(Embeddings):
    """Expose a RepoAgent ``EmbeddingProvider`` as LangChain ``Embeddings``."""

    def __init__(self, provider: EmbeddingProvider) -> None:
        self.provider = provider

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.provider.embed(texts)

    def embed_query(self, text: str) -> list[float]:
        return self.provider.embed([text])[0]


class LangChainEmbeddingProvider:
    """Use any LangChain ``Embeddings`` as a RepoAgent ``EmbeddingProvider``.

    ``name`` and ``dimension`` travel with the index, so a snapshot built
    with one model is never silently searched with another.
    """

    def __init__(self, embeddings: Embeddings, *, name: str, dimension: int) -> None:
        self._embeddings, self.name, self.dimension = embeddings, name, dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._embeddings.embed_documents(texts) if texts else []
