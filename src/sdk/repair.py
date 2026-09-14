"""Public SDK capability for M6 static repair proposals."""

from pathlib import Path

from repoagent.ai.openai_provider import llm_provider_from_settings
from repoagent.ai.provider import LLMProvider
from repoagent.application.repair import RepairRequest, RepairService
from repoagent.config import Settings
from repoagent.domain.investigation import Issue
from repoagent.domain.repair import RepairReport
from repoagent.sdk.retrieval import RetrievalApi


class RepairApi:
    def __init__(self, settings: Settings, retrieval: RetrievalApi) -> None:
        self._settings, self._retrieval = settings, retrieval

    def repair(
        self,
        source: str | Path,
        issue: Issue | str,
        *,
        max_revisions: int | None = None,
        provider: LLMProvider | None = None,
    ) -> RepairReport:
        settings = self._settings
        request = RepairRequest(
            repository=str(source),
            issue=issue,
            max_revisions=max_revisions
            if max_revisions is not None
            else settings.repair_max_revisions,
        )
        store, embedding = self._retrieval._services()
        llm = provider or llm_provider_from_settings(settings)
        return RepairService(store, embedding, llm).repair(request)
