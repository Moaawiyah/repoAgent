"""Hands the best VERIFIED candidate to the existing repair pipeline.

No new repair logic: this only picks a candidate and converts it to the
existing ``Issue`` model, then calls the unchanged M6 ``RepairService``.
"""

from repoagent.ai.provider import LLMProvider
from repoagent.application.repair import RepairRequest, RepairService
from repoagent.domain.audit import CandidateIssue, VerificationStatus
from repoagent.domain.repair import RepairReport
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
