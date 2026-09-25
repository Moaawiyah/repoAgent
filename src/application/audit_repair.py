"""Hands the best VERIFIED candidate to the existing repair pipelines.

No new repair logic: this only picks a candidate and converts it to the
existing ``Issue`` model, then calls the unchanged M6 ``RepairService``
(static proposal) or the unchanged M7 validated repair (``--execute``).
"""

from collections.abc import Callable

from repoagent.ai.provider import LLMProvider
from repoagent.application.repair import RepairRequest, RepairService
from repoagent.domain.audit import CandidateIssue, VerificationStatus
from repoagent.domain.audit_report import AuditReport
from repoagent.domain.investigation import Issue
from repoagent.domain.repair import RepairReport
from repoagent.domain.repair_execution import ValidatedRepairReport
from repoagent.ports.index_store import IndexStore
from repoagent.retrieval.embeddings import EmbeddingProvider


def _confidence(candidate: CandidateIssue) -> float:
    """Prefer the verifier's post-evidence confidence over the detector's."""
    return (
        candidate.verification.confidence
        if candidate.verification
        else candidate.confidence
    )


def best_verified(candidates: list[CandidateIssue]) -> CandidateIssue | None:
    verified = [c for c in candidates if c.status == VerificationStatus.VERIFIED]
    return max(verified, key=_confidence, default=None)


def repair_best_candidate(
    store: IndexStore,
    embedding: EmbeddingProvider,
    llm: LLMProvider,
    repository: str,
    candidates: list[CandidateIssue],
) -> tuple[RepairReport | None, str]:
    """Repair the highest-confidence verified candidate, if any."""
    candidate = best_verified(candidates)
    if candidate is None:
        return None, "no_verified_candidate"
    report = RepairService(store, embedding, llm).repair(
        RepairRequest(repository=repository, issue=candidate.to_issue())
    )
    return report, report.status.value


def validate_best_candidate(
    report: AuditReport, repair: Callable[[Issue], ValidatedRepairReport]
) -> AuditReport:
    """Run M7 on the best VERIFIED finding and attach the validated outcome.

    ``repair`` is the existing validated repair entry point (investigate,
    develop, review, Docker validation, retry/failure analysis), which
    works on a disposable sandbox copy, never on the audited checkout.
    """
    candidate = best_verified(report.candidates)
    if candidate is None:
        metrics = report.metrics.model_copy(
            update={"repair_status": "no_verified_candidate"}
        )
        return report.model_copy(update={"metrics": metrics})
    validated = repair(candidate.to_issue())
    metrics = report.metrics.model_copy(
        update={"repair_status": validated.status.value}
    )
    return report.model_copy(
        update={
            "validated_repair": validated,
            "repair_candidate_id": candidate.id,
            "metrics": metrics,
        }
    )
