"""Assemble a SearchService from settings plus per-call overrides."""

from repoagent.ai.provider import LLMProvider
from repoagent.application.searching import SearchService
from repoagent.config import Settings
from repoagent.ports.index_store import IndexStore
from repoagent.retrieval.configured import build_reranker, graph_policy_from_settings
from repoagent.retrieval.embeddings import EmbeddingProvider
from repoagent.retrieval.rerank import Reranker


def configured_search(
    settings: Settings,
    store: IndexStore,
    embedding: EmbeddingProvider,
    *,
    graph_policy: str | None = None,
    reranker: str | Reranker | None = None,
    llm: LLMProvider | None = None,
    rerank_candidates: int | None = None,
) -> SearchService:
    """Graph policy and reranker default to settings; names override them.

    The LLM provider is only built from settings when the ``llm``
    reranker is actually selected, so other searches stay offline.
    """
    chosen = reranker or settings.reranker
    if isinstance(chosen, str):
        if chosen == "llm" and llm is None:
            from repoagent.ai.openai_provider import llm_provider_from_settings

            llm = llm_provider_from_settings(settings)
        chosen = build_reranker(chosen, embedding, llm)
    return SearchService(
        store,
        embedding,
        reranker=chosen,
        graph_policy=graph_policy_from_settings(settings, graph_policy),
        rerank_candidates=rerank_candidates or settings.rerank_candidates,
    )
