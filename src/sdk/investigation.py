"""Typed investigation capability, composing the independent M5 service."""

from pathlib import Path

from repoagent.adapters.investigation_store import InvestigationStore
from repoagent.ai.openai_provider import llm_provider_from_settings
from repoagent.ai.provider import LLMProvider
from repoagent.application.investigation import InvestigateRequest, InvestigationService
from repoagent.config import Settings
from repoagent.domain.investigation import (
    InvestigationLimits,
    InvestigationReport,
    Issue,
)
from repoagent.retrieval.configured import graph_policy_from_settings
from repoagent.sdk.retrieval import RetrievalApi


class InvestigationApi:
    """SDK capability split to keep the public facade focused and small."""

    def __init__(self, settings: Settings, retrieval: RetrievalApi) -> None:
        self._settings, self._retrieval = settings, retrieval

    def investigate(
        self,
        source: str | Path,
        issue: Issue | str,
        *,
        max_iterations: int | None = None,
        top_k: int = 5,
        provider: LLMProvider | None = None,
        use_graph: bool = True,
    ) -> InvestigationReport:
        request = InvestigateRequest(
            repository=str(source),
            issue=issue,
            max_iterations=max_iterations,
            top_k=top_k,
            use_graph=use_graph,
        )
        settings = self._settings or Settings()
        store, embedding = self._retrieval._services()
        limits = InvestigationLimits(
            max_iterations=settings.investigation_max_iterations,
            max_queries=settings.investigation_max_queries,
            max_evidence=settings.investigation_max_evidence,
            max_tool_calls=settings.investigation_max_tool_calls,
            context_chars=settings.investigation_context_chars,
        )
        llm = provider or llm_provider_from_settings(settings)
        policy = graph_policy_from_settings(settings)
        report = InvestigationService(store, embedding, llm, policy).investigate(
            request, limits
        )
        InvestigationStore(settings.data_dir / "investigations").save(report)
        return report
