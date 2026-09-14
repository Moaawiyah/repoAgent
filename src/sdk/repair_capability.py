"""Small public SDK mixin for the M6 repair capability."""

from pathlib import Path
from typing import Protocol

from repoagent.ai.provider import LLMProvider
from repoagent.config import Settings
from repoagent.domain.investigation import Issue
from repoagent.domain.repair import RepairReport
from repoagent.domain.repair_execution import ValidatedRepairReport
from repoagent.ports.sandbox import SandboxRunner
from repoagent.sdk.repair import RepairApi
from repoagent.sdk.retrieval import RetrievalApi
from repoagent.sdk.validated_repair import ValidatedRepairApi


class RepairClient(Protocol):
    """Internal capability requirements supplied by the main SDK facade."""

    _settings: Settings | None
    _sandbox_runner: SandboxRunner | None

    def retrieval(self) -> RetrievalApi: ...


class RepairCapability:
    """Keeps repair construction separate from the general SDK facade."""

    def repair(
        self: RepairClient,
        source: str | Path,
        issue: Issue | str,
        *,
        max_revisions: int | None = None,
        provider: LLMProvider | None = None,
    ) -> RepairReport:
        """Propose/review an unapplied static patch (M6)."""
        return RepairApi(self._settings or Settings(), self.retrieval()).repair(
            source, issue, max_revisions=max_revisions, provider=provider
        )

    def repair_and_validate(
        self: RepairClient,
        source: str | Path,
        issue: Issue | str,
        *,
        max_attempts: int | None = None,
        max_revisions: int | None = None,
        timeout: int | None = None,
        provider: LLMProvider | None = None,
    ) -> ValidatedRepairReport:
        """Repair, execute validation in an isolated sandbox, and retry (M7).

        The original repository is never modified; ``VALIDATED`` is returned
        only when required validation of the patched copy succeeds.
        """
        api = ValidatedRepairApi(
            self._settings or Settings(), self.retrieval(), self._sandbox_runner
        )
        return api.repair(
            source,
            issue,
            max_attempts=max_attempts,
            max_revisions=max_revisions,
            timeout=timeout,
            provider=provider,
        )
