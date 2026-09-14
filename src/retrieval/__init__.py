"""Hybrid code retrieval: chunking, BM25, embeddings, fusion (M3)."""

from repoagent.retrieval.bm25 import BM25Index, BM25Retriever
from repoagent.retrieval.chunking import CodeChunker
from repoagent.retrieval.embeddings import (
    EmbeddingProvider,
    HashingEmbeddingProvider,
    provider_from_settings,
)
from repoagent.retrieval.models import (
    CodeChunk,
    RetrievalResult,
    RetrievalSource,
    RetrievalStrategy,
    SearchRequest,
    SearchResponse,
    make_chunk_id,
    repository_identifier,
)
from repoagent.retrieval.persistence import IndexSnapshot, IndexSummary
from repoagent.retrieval.rerank import KeywordOverlapReranker, Reranker
from repoagent.retrieval.retrievers import (
    HybridRetriever,
    Retriever,
    VectorRetriever,
    build_retriever,
)
from repoagent.retrieval.vector_store import LocalVectorStore, VectorStore

__all__ = [
    "BM25Index",
    "BM25Retriever",
    "CodeChunk",
    "CodeChunker",
    "EmbeddingProvider",
    "HashingEmbeddingProvider",
    "HybridRetriever",
    "IndexSnapshot",
    "IndexSummary",
    "KeywordOverlapReranker",
    "LocalVectorStore",
    "Reranker",
    "Retriever",
    "RetrievalResult",
    "RetrievalSource",
    "RetrievalStrategy",
    "SearchRequest",
    "SearchResponse",
    "VectorRetriever",
    "VectorStore",
    "build_retriever",
    "make_chunk_id",
    "provider_from_settings",
    "repository_identifier",
]
