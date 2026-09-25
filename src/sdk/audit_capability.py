"""Small public SDK mixin for the repository audit capability."""

from pathlib import Path
from typing import Protocol

from repoagent.ai.provider import LLMProvider
from repoagent.config import Settings
from repoagent.domain.audit_report import AuditReport
from repoagent.ports.sandbox import SandboxRunner
from repoagent.sdk.audit import AuditApi
from repoagent.sdk.retrieval import RetrievalApi


class AuditClient(Protocol):
    """Internal capability requirements supplied by the main SDK facade."""

    _settings: Settings | None
    _sandbox_runner: SandboxRunner | None

    def retrieval(self) -> RetrievalApi: ...


class AuditCapability:
    """Keeps audit construction separate from the general SDK facade."""

    def audit(
        self: AuditClient,
        source: str | Path,
        *,
        limit: int | None = None,
        repair: bool = False,
        execute: bool = False,
        max_attempts: int | None = None,
        timeout: int | None = None,
        provider: LLMProvider | None = None,
    ) -> AuditReport:
        """Discover, verify, and (optionally) repair candidate issues.

        ``execute=True`` (requires ``repair``) validates the repair of the
        best verified finding in the M7 Docker sandbox.
        """
        api = AuditApi(
            self._settings or Settings(), self.retrieval(), self._sandbox_runner
        )
        return api.audit(
            source,
            limit=limit,
            repair=repair,
            execute=execute,
            max_attempts=max_attempts,
            timeout=timeout,
            provider=provider,
        )
