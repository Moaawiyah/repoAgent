"""Repository audit orchestration: discover, dedupe, enrich, verify, repair.

Detection/dedup/evidence/verification each live in their own module
(``audit.*``, ``application.audit_evidence``, ``application.audit_verification``,
``application.audit_repair``); this service only sequences them.
"""

import logging
from pathlib import Path

from pydantic import Field

from repoagent.ai.provider import LLMProvider, require_provider
from repoagent.analysis.analyzer import RepositoryAnalyzer
from repoagent.analysis.models import AnalysisModel
from repoagent.application.audit_evidence import attach_evidence
from repoagent.application.audit_repair import repair_best_candidate
from repoagent.application.audit_verification import verify_candidates
from repoagent.audit.context import AuditContext
from repoagent.audit.dedupe import deduplicate
from repoagent.audit.detectors import default_detectors
from repoagent.domain.audit import CandidateIssue
from repoagent.domain.audit_report import AuditReport
from repoagent.domain.repository import RepositorySpec
from repoagent.graph.builder import RepositoryGraphBuilder
from repoagent.ports.index_store import IndexStore
from repoagent.ports.sandbox import SandboxRunner
from repoagent.retrieval.embeddings import EmbeddingProvider

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
        spec = RepositorySpec(source=request.repository)
        analysis = RepositoryAnalyzer().analyze(spec)
        root = Path(analysis.repository_root)
        graph_store = RepositoryGraphBuilder().build(analysis)
        context = AuditContext(analysis, root, graph_store)

        candidates, by_source = self._discover(context)
        deduped, removed = deduplicate(candidates)
        deduped.sort(key=lambda c: -c.confidence)
        if request.limit is not None:
            deduped = deduped[: request.limit]

        enriched = attach_evidence(
            self._store, self._embedding, request.repository, root, graph_store, deduped
        )
        provider = require_provider(self._llm, "audits")
        verified, metrics = verify_candidates(provider, enriched)
        metrics = metrics.model_copy(
            update={
                "candidates_generated": len(candidates),
                "candidates_by_source": by_source,
                "duplicate_findings_removed": removed,
            }
        )

        repair_report = None
        if request.repair:
            repair_report, status = repair_best_candidate(
                self._store, self._embedding, provider, request.repository, verified
            )
            metrics = metrics.model_copy(update={"repair_status": status})

        LOGGER.info(
            "Audit completed",
            extra={"event": "audit_completed", "candidates": len(verified)},
        )
        return AuditReport(
            repository=request.repository,
            files_scanned=analysis.python_files,
            symbols_scanned=len(analysis.symbols),
            candidates=verified,
            metrics=metrics,
            repair=repair_report,
        )

    def _discover(
        self, context: AuditContext
    ) -> tuple[list[CandidateIssue], dict[str, int]]:
        candidates: list[CandidateIssue] = []
        by_source: dict[str, int] = {}
        for detector in default_detectors(self._sandbox_runner):
            found = detector.detect(context)
            candidates.extend(found)
            by_source[detector.name] = by_source.get(detector.name, 0) + len(found)
        return candidates, by_source
