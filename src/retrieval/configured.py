"""Build configured retrieval components: graph policy and reranker."""

from repoagent.ai.provider import LLMProvider, require_provider
from repoagent.config import Settings
from repoagent.graph.policy import GraphPolicy, graph_policy
from repoagent.retrieval.embeddings import EmbeddingProvider
from repoagent.retrieval.rerank import KeywordOverlapReranker, Reranker

RERANKERS = ("keyword", "semantic", "llm")


def graph_policy_from_settings(
    settings: Settings, name: str | None = None
) -> GraphPolicy:
    """The named (or configured) preset with any configured overrides."""
    return graph_policy(
        name or settings.graph_policy,
        edge_weights=settings.graph_edge_weights or None,
        unresolved_weight=settings.graph_unresolved_weight,
        max_depth=settings.graph_max_depth,
    )


def build_reranker(
    name: str, embedding: EmbeddingProvider, llm: LLMProvider | None = None
) -> Reranker:
    """Instantiate a reranker by name; ``llm`` needs a configured provider."""
    if name == "keyword":
        return KeywordOverlapReranker()
    from repoagent.retrieval.model_rerank import LLMReranker, SemanticReranker

    if name == "semantic":
        return SemanticReranker(embedding)
    if name == "llm":
        return LLMReranker(require_provider(llm, "LLM reranking"))
    raise ValueError(f"Unknown reranker: {name}; expected one of {RERANKERS}")
