"""Framework-independent M6 patch planning, validation, and review models."""

from enum import StrEnum

from pydantic import Field

from repoagent.analysis.models import AnalysisModel
from repoagent.domain.investigation import InvestigationReport


class PatchPlan(AnalysisModel):
    """Smallest intended evidence-backed code change."""

    summary: str = Field(min_length=1, max_length=800)
    affected_files: list[str] = Field(min_length=1, max_length=10)
    affected_symbols: list[str] = Field(default_factory=list, max_length=10)
    assumptions: list[str] = Field(default_factory=list, max_length=8)
    risks: list[str] = Field(default_factory=list, max_length=8)
    recommended_tests: list[str] = Field(default_factory=list, max_length=10)


class PatchProposal(AnalysisModel):
    """Unapplied unified diff and its typed plan."""

    plan: PatchPlan
    unified_diff: str = Field(min_length=1, max_length=20000)


class StaticValidation(AnalysisModel):
    """Deterministic validation of an in-memory patch application."""

    valid: bool
    errors: list[str] = Field(default_factory=list, max_length=30)
    changed_files: list[str] = Field(default_factory=list, max_length=10)
    changed_lines: int = Field(default=0, ge=0)


class ReviewDecision(StrEnum):
    APPROVE = "approve"
    REVISE = "revise"
    REJECT = "reject"


class PatchReview(AnalysisModel):
    """Independent review with concise observable rationale only."""

    decision: ReviewDecision
    rationale: str = Field(min_length=1, max_length=1000)
    concerns: list[str] = Field(default_factory=list, max_length=10)
    recommended_tests: list[str] = Field(default_factory=list, max_length=10)


class RepairStatus(StrEnum):
    APPROVED_FOR_RUNTIME_VALIDATION = "approved_for_runtime_validation"
    REJECTED = "rejected"
    MAX_REVISIONS = "max_revisions"
    INSUFFICIENT_INVESTIGATION = "insufficient_investigation"
    PROVIDER_ERROR = "provider_error"


class RepairReport(AnalysisModel):
    """M6 read-only output; no patch has been applied or executed."""

    investigation: InvestigationReport
    status: RepairStatus
    proposal: PatchProposal | None = None
    validation: StaticValidation | None = None
    reviews: list[PatchReview] = Field(default_factory=list)
    revisions: int = Field(default=0, ge=0)
    error: str | None = None
