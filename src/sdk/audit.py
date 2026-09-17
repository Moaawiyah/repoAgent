"""Public SDK capability for repository audit / issue discovery."""

from pathlib import Path

from repoagent.ai.openai_provider import llm_provider_from_settings
from repoagent.ai.provider import LLMProvider
from repoagent.application.audit import AuditRequest, AuditService
from repoagent.config import Settings
from repoagent.domain.audit_report import AuditReport
from repoagent.ports.sandbox import SandboxRunner
from repoagent.sdk.retrieval import RetrievalApi


class AuditApi:
    """SDK capability split to keep the public facade focused and small."""

    def __init__(
        self,
        settings: Settings,
        retrieval: RetrievalApi,
        sandbox_runner: SandboxRunner | None = None,
    ) -> None:
        self._settings, self._retrieval = settings, retrieval
        self._sandbox_runner = sandbox_runner

    def audit(
        self,
        source: str | Path,
        *,
        limit: int | None = None,
        repair: bool = False,
        provider: LLMProvider | None = None,
    ) -> AuditReport:
        request = AuditRequest(repository=str(source), limit=limit, repair=repair)
        settings = self._settings or Settings()
        store, embedding = self._retrieval._services()
        llm = provider or llm_provider_from_settings(settings)
        service = AuditService(store, embedding, llm, self._sandbox_runner)
        return service.audit(request)
