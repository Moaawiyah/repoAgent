"""Audit-run metrics and the top-level report returned to callers."""

from pydantic import Field

from repoagent.analysis.models import AnalysisModel
from repoagent.domain.audit import CandidateIssue, VerificationStatus
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
