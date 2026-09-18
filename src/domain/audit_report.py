"""Audit-run metrics and the top-level report returned to callers."""

from pydantic import Field, model_validator

from repoagent.analysis.models import AnalysisModel
from repoagent.domain.audit import CandidateIssue, VerificationStatus
from repoagent.domain.errors import AuditError
from repoagent.domain.investigation import Issue
from repoagent.domain.repair import RepairReport


class AuditMetrics(AnalysisModel):
    """Measured counters for later detector precision/false-positive analysis."""

    candidates_generated: int = 0
    candidates_by_source: dict[str, int] = Field(default_factory=dict)
    duplicate_findings_removed: int = 0
    verified: int = 0
    uncertain: int = 0
    rejected: int = 0
    verification_llm_calls: int = 0
    verification_input_tokens: int = 0
    verification_output_tokens: int = 0
    verification_duration_seconds: float = 0.0
    repair_status: str | None = None


class AuditReport(AnalysisModel):
    """Full audit outcome; candidates carry their own verification status."""

    repository: str
    files_scanned: int = 0
    symbols_scanned: int = 0
    candidates: list[CandidateIssue] = Field(default_factory=list)
    metrics: AuditMetrics = Field(default_factory=AuditMetrics)
    repair: RepairReport | None = None
    error: str | None = None

    def by_status(self, status: VerificationStatus) -> list[CandidateIssue]:
        return [c for c in self.candidates if c.status == status]


class VerifiedIssue(AnalysisModel):
    """A VERIFIED finding: the only kind that may be handed to repair."""

    candidate: CandidateIssue

    @model_validator(mode="after")
    def _require_verified(self) -> "VerifiedIssue":
        if self.candidate.status != VerificationStatus.VERIFIED:
            raise ValueError("Only VERIFIED findings can be repaired")
        return self

    @classmethod
    def from_report(cls, report: AuditReport, candidate_id: str) -> "VerifiedIssue":
        match = next((c for c in report.candidates if c.id == candidate_id), None)
        if match is None:
            raise AuditError("Finding not found in this discovery result")
        if match.status != VerificationStatus.VERIFIED:
            raise AuditError("Only VERIFIED findings can be sent to repair")
        return cls(candidate=match)

    def to_issue(self) -> Issue:
        return self.candidate.to_issue()
