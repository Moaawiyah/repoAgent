"""Repository audit orchestration: discover, dedupe, enrich, verify, repair.

Discovery runs as the ``DiscoveryGraph`` LangGraph workflow (detectors,
dedup, RAG evidence, verifier — each an existing module); this service
adds only the optional, explicitly requested repair of the best finding.
"""

import logging

from pydantic import Field

from repoagent.ai.provider import LLMProvider, require_provider
from repoagent.analysis.models import AnalysisModel
from repoagent.application.audit_repair import repair_best_candidate
from repoagent.domain.audit_report import AuditReport
from repoagent.ports.index_store import IndexStore
from repoagent.ports.sandbox import SandboxRunner
from repoagent.retrieval.embeddings import EmbeddingProvider
from repoagent.workflows.discovery_graph import DiscoveryGraph
from repoagent.workflows.discovery_nodes import DiscoveryDeps

LOGGER = logging.getLogger(__name__)


class AuditRequest(AnalysisModel):
    """Validated audit input."""

    repository: str
    limit: int | None = Field(default=None, ge=1, le=200)
    repair: bool = False


class AuditService:
    """Discovers, verifies, and (optionally) repairs candidate issues."""

    def __init__(
        self,
        store: IndexStore,
        embedding: EmbeddingProvider,
        llm: LLMProvider | None,
        sandbox_runner: SandboxRunner | None = None,
    ) -> None:
        self._store, self._embedding, self._llm = store, embedding, llm
        self._sandbox_runner = sandbox_runner

    def audit(self, request: AuditRequest) -> AuditReport:
        deps = DiscoveryDeps(
            self._store, self._embedding, self._llm, self._sandbox_runner
        )
        state = DiscoveryGraph(deps).run(request.repository, request.limit)
        report = DiscoveryGraph.report(state, request.repository)
        if request.repair:
            provider = require_provider(self._llm, "audits")
            repair_report, status = repair_best_candidate(
                self._store,
                self._embedding,
                provider,
                request.repository,
                report.candidates,
            )
            metrics = report.metrics.model_copy(update={"repair_status": status})
            report = report.model_copy(
                update={"repair": repair_report, "metrics": metrics}
            )
        LOGGER.info(
            "Audit completed",
            extra={"event": "audit_completed", "candidates": len(report.candidates)},
        )
        return report
