"""Sandboxed repair attempts, failure analysis, metrics and final report (M7)."""

from enum import StrEnum

from pydantic import Field

from repoagent.analysis.models import AnalysisModel
from repoagent.domain.investigation import InvestigationReport
from repoagent.domain.repair import PatchProposal, PatchReview, StaticValidation
from repoagent.domain.sandbox import ValidationPlan
from repoagent.domain.validation import ValidationResult


class FailureCategory(StrEnum):
    TEST_FAILURE = "test_failure"
    REGRESSION = "regression"
    LINT = "lint"
    COLLECTION_ERROR = "collection_error"
    TIMEOUT = "timeout"
    PRE_EXISTING = "pre_existing"
    WRONG_ROOT_CAUSE = "wrong_root_cause"
    UNKNOWN = "unknown"


class NextAction(StrEnum):
    REVISE_PATCH = "revise_patch"
    REINVESTIGATE = "reinvestigate"
    STOP = "stop"


class FailureAnalysis(AnalysisModel):
    """Concise structured diagnosis; never hidden chain-of-thought."""

    category: FailureCategory
    likely_reason: str = Field(min_length=1, max_length=800)
    affected_file: str | None = Field(default=None, max_length=300)
    affected_symbol: str | None = Field(default=None, max_length=300)
    patch_caused_failure: bool
    next_action: NextAction
    evidence_needed: list[str] = Field(default_factory=list, max_length=6)
    source: str = Field(default="deterministic", pattern="^(deterministic|llm)$")


class RepairAttempt(AnalysisModel):
    """One approved patch executed in a fresh disposable workspace."""

    number: int = Field(ge=1)
    proposal: PatchProposal
    static_validation: StaticValidation
    reviews: list[PatchReview] = Field(default_factory=list)
    validation: ValidationResult
    failure_analysis: FailureAnalysis | None = None
    failure_summary: str = Field(default="", max_length=1000)


class ExecutionStatus(StrEnum):
    VALIDATED = "validated"
    VALIDATION_FAILED = "validation_failed"
    PATCH_APPLY_FAILED = "patch_apply_failed"
    SANDBOX_FAILED = "sandbox_failed"
    TIMEOUT = "timeout"
    MAX_ATTEMPTS = "max_attempts"
    BASELINE_FAILED = "baseline_failed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    VALIDATION_UNAVAILABLE = "validation_unavailable"
    REVIEW_REJECTED = "review_rejected"
    PROVIDER_ERROR = "provider_error"


class RepairMetrics(AnalysisModel):
    """Measured per-repair counters consumed by later benchmarking."""

    attempts: int = 0
    llm_calls: int = 0
    retrieval_calls: int = 0
    investigations: int = 0
    files_changed: int = 0
    lines_changed: int = 0
    validation_seconds: float = 0.0
    sandbox_seconds: float = 0.0
    tests_before: dict[str, int] | None = None
    tests_after: dict[str, int] | None = None
    final_status: ExecutionStatus


class ValidatedRepairReport(AnalysisModel):
    """M7 output; VALIDATED only when required sandbox validation succeeded."""

    task_id: str
    repository: str
    status: ExecutionStatus
    investigation: InvestigationReport | None = None
    plan: ValidationPlan | None = None
    baseline: ValidationResult | None = None
    attempts: list[RepairAttempt] = Field(default_factory=list)
    final_proposal: PatchProposal | None = None
    reviews: list[PatchReview] = Field(default_factory=list)
    reinvestigations: int = 0
    metrics: RepairMetrics
    error: str | None = Field(default=None, max_length=1000)
