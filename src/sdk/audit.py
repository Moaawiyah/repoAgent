"""Public SDK capability for repository audit / issue discovery."""

from pathlib import Path

from repoagent.ai.openai_provider import llm_provider_from_settings
from repoagent.ai.provider import LLMProvider
from repoagent.application.audit import AuditRequest, AuditService
from repoagent.application.audit_repair import validate_best_candidate
from repoagent.config import Settings
from repoagent.domain.audit_report import AuditReport
from repoagent.domain.errors import AuditError
from repoagent.ports.sandbox import SandboxRunner
from repoagent.sdk.retrieval import RetrievalApi
from repoagent.sdk.validated_repair import ValidatedRepairApi


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
        execute: bool = False,
        max_attempts: int | None = None,
        timeout: int | None = None,
        provider: LLMProvider | None = None,
    ) -> AuditReport:
        """Audit; ``repair`` proposes a static fix, ``execute`` validates it.

        With ``execute`` the best VERIFIED finding goes through the full M7
        validated repair (Docker sandbox copy; the checkout is untouched).
        """
        if execute and not repair:
            raise AuditError("execute requires repair")
        static = repair and not execute
        request = AuditRequest(repository=str(source), limit=limit, repair=static)
        settings = self._settings or Settings()
        store, embedding = self._retrieval._services()
        llm = provider or llm_provider_from_settings(settings)
        service = AuditService(store, embedding, llm, self._sandbox_runner)
        report = service.audit(request)
        if not execute:
            return report
        validated = ValidatedRepairApi(settings, self._retrieval, self._sandbox_runner)
        return validate_best_candidate(
            report,
            lambda issue: validated.repair(
                source,
                issue,
                max_attempts=max_attempts,
                timeout=timeout,
                provider=llm,
            ),
        )
