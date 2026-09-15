"""M7 application service: investigation, repair loop, sandboxed validation.

Cheap deterministic gates run first (index exists, validation detectable,
sandbox available) so no LLM tokens are spent when execution cannot happen.
"""

import logging
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, field_validator

from repoagent.agent.execution_agent import ExecutionRepairAgent
from repoagent.agent.execution_state import RepairLoopLimits
from repoagent.ai.counting import CountingProvider
from repoagent.ai.provider import LLMProvider, require_provider
from repoagent.application.investigation import InvestigateRequest, InvestigationService
from repoagent.application.repair_outcomes import early_report
from repoagent.application.searching import SearchService
from repoagent.domain.errors import SandboxError
from repoagent.domain.features import RepairFeatures
from repoagent.domain.investigation import (
    InvestigationLimits,
    InvestigationReport,
    Issue,
    TerminationReason,
)
from repoagent.domain.repair_execution import ValidatedRepairReport
from repoagent.domain.sandbox import CommandKind, SandboxLimits
from repoagent.ports.index_store import IndexStore
from repoagent.ports.sandbox import SandboxRunner
from repoagent.retrieval.embeddings import EmbeddingProvider
from repoagent.validation.detection import ProjectDetector

LOGGER = logging.getLogger(__name__)


class ValidatedRepairRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    repository: str
    issue: Issue
    loop: RepairLoopLimits = RepairLoopLimits()
    sandbox: SandboxLimits = SandboxLimits()
    features: RepairFeatures = RepairFeatures()

    @field_validator("issue", mode="before")
    @classmethod
    def _coerce_issue(cls, value: Issue | str) -> Issue:
        return Issue(description=value) if isinstance(value, str) else value


class ValidatedRepairService:
    def __init__(
        self,
        store: IndexStore,
        embedding: EmbeddingProvider,
        provider: LLMProvider | None,
        runner: SandboxRunner,
        investigation_limits: InvestigationLimits | None = None,
    ) -> None:
        self._store, self._embedding, self._provider = store, embedding, provider
        self._runner, self._limits = runner, investigation_limits

    def repair(self, request: ValidatedRepairRequest) -> ValidatedRepairReport:
        provider = CountingProvider(require_provider(self._provider, "repairs"))
        snapshot = SearchService(self._store, self._embedding).snapshot(
            request.repository
        )
        root = Path(snapshot.repository_root)
        task_id = uuid4().hex
        plan = ProjectDetector(request.sandbox).detect(root)
        if not plan.has(CommandKind.PYTEST):
            return early_report(task_id, request.repository, plan, provider, None)

        features = request.features
        loop = request.loop
        if not features.failure_retry:
            loop = loop.model_copy(
                update={"max_attempts": 1, "max_reinvestigations": 0}
            )

        def investigate(issue: Issue) -> InvestigationReport:
            service = InvestigationService(self._store, self._embedding, provider)
            return service.investigate(
                InvestigateRequest(
                    repository=request.repository,
                    issue=issue,
                    use_graph=features.graph_retrieval,
                    max_iterations=1 if features.single_retrieval_pass else None,
                ),
                self._limits,
            )

        investigation = None
        try:
            with self._runner.session(root, plan, request.sandbox) as session:
                investigation = investigate(request.issue)
                reason = investigation.termination_reason
                if reason != TerminationReason.CONFIDENT_ROOT_CAUSE:
                    return early_report(
                        task_id, request.repository, plan, provider, investigation
                    )
                agent = ExecutionRepairAgent(
                    provider, session, investigate, loop, features.reviewer
                )
                return agent.run(task_id, investigation, plan)
        except SandboxError as error:
            LOGGER.warning(
                "Sandbox failed",
                extra={"event": "sandbox_failed", "task_id": task_id},
            )
            return early_report(
                task_id, request.repository, plan, provider, investigation, str(error)
            )
