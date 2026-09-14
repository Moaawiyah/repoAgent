"""Small public SDK mixin for the M6 repair capability."""

from pathlib import Path
from typing import Protocol

from repoagent.ai.provider import LLMProvider
from repoagent.config import Settings
from repoagent.domain.investigation import Issue
from repoagent.domain.repair import RepairReport
from repoagent.sdk.repair import RepairApi
from repoagent.sdk.retrieval import RetrievalApi


class RepairClient(Protocol):
    """Internal capability requirements supplied by the main SDK facade."""

    _settings: Settings | None

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
