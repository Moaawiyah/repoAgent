"""M6 application service composing existing investigation with repair review."""

from pydantic import Field, field_validator

from repoagent.agent.repair_agent import RepairAgent
from repoagent.ai.provider import LLMProvider, require_provider
from repoagent.analysis.models import AnalysisModel
from repoagent.application.investigation import InvestigateRequest, InvestigationService
from repoagent.domain.investigation import Issue, TerminationReason
from repoagent.domain.repair import RepairReport, RepairStatus
from repoagent.ports.index_store import IndexStore
from repoagent.retrieval.embeddings import EmbeddingProvider


class RepairRequest(AnalysisModel):
    repository: str
    issue: Issue
    max_revisions: int = Field(default=2, ge=0, le=5)

    @field_validator("issue", mode="before")
    @classmethod
    def _coerce_issue(cls, value: Issue | str) -> Issue:
        return Issue(description=value) if isinstance(value, str) else value


class RepairService:
    """Runs M5 before bounded static-only M6 review."""

    def __init__(
        self,
        store: IndexStore,
        embedding: EmbeddingProvider,
        provider: LLMProvider | None,
    ) -> None:
        self._store, self._embedding, self._provider = store, embedding, provider

    def repair(self, request: RepairRequest) -> RepairReport:
        provider = require_provider(self._provider, "repairs")
        investigation = InvestigationService(
            self._store, self._embedding, provider
        ).investigate(
            InvestigateRequest(repository=request.repository, issue=request.issue)
        )
        if investigation.termination_reason != TerminationReason.CONFIDENT_ROOT_CAUSE:
            return RepairReport(
                investigation=investigation,
                status=RepairStatus.INSUFFICIENT_INVESTIGATION,
                error=(
                    "No patch proposed because investigation lacks a "
                    "confident root cause."
                ),
            )
        return RepairAgent(request.repository, provider, request.max_revisions).run(
            investigation
        )
