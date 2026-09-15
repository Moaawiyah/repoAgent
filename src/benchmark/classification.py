"""Deterministic failure categories from measured outcomes (no LLM judge)."""

from repoagent.benchmark.results import FailureCategory as F
from repoagent.benchmark.results import Localization
from repoagent.domain.investigation import InvestigationReport, TerminationReason
from repoagent.domain.repair_execution import ExecutionStatus as S
from repoagent.domain.repair_execution import ValidatedRepairReport

_DIRECT = {
    S.PATCH_APPLY_FAILED: F.PATCH_APPLY_FAILURE,
    S.TIMEOUT: F.TIMEOUT,
    S.SANDBOX_FAILED: F.SANDBOX_FAILURE,
    S.BASELINE_FAILED: F.SANDBOX_FAILURE,
    S.PROVIDER_ERROR: F.PROVIDER_ERROR,
    S.VALIDATION_UNAVAILABLE: F.VALIDATION_UNAVAILABLE,
}


def classify_investigation(
    report: InvestigationReport, located: Localization, expected_files: list[str]
) -> F | None:
    """Investigate mode succeeds when the primary hypothesis cites a gold file."""
    if report.termination_reason == TerminationReason.PROVIDER_ERROR:
        return F.PROVIDER_ERROR
    if located.file_hit:
        return None
    retrieved = {item.file_path for item in report.evidence}
    if not retrieved & set(expected_files):
        return F.LOCALIZATION_FAILURE
    if report.termination_reason != TerminationReason.CONFIDENT_ROOT_CAUSE:
        return F.INSUFFICIENT_EVIDENCE
    return F.INCORRECT_ROOT_CAUSE


def classify_repair(
    report: ValidatedRepairReport,
    located: Localization,
    expected_files: list[str],
    hidden_passed: bool | None,
) -> F | None:
    """Repair succeeds only when validated and hidden tests (if any) pass."""
    if report.status in _DIRECT:
        return _DIRECT[report.status]
    if report.status == S.INSUFFICIENT_EVIDENCE and report.investigation:
        return (
            classify_investigation(report.investigation, located, expected_files)
            or F.INSUFFICIENT_EVIDENCE
        )
    if report.status == S.REVIEW_REJECTED:
        attempt_static = (
            report.reviews
            and "Static patch validation failed" in report.reviews[-1].rationale
        )
        return F.PATCH_GENERATION_FAILURE if attempt_static else F.REVIEW_REJECTION
    last = report.attempts[-1] if report.attempts else None
    if report.status == S.VALIDATED:
        if hidden_passed is not False:
            return None
        touched = set(last.static_validation.changed_files) if last else set()
        return (
            F.TEST_FAILURE if touched & set(expected_files) else F.INCORRECT_ROOT_CAUSE
        )
    comparison = last.validation.comparison if last else None
    if comparison and comparison.new_failures:
        return F.REGRESSION
    analysis = last.failure_analysis if last else None
    if analysis and analysis.category == "wrong_root_cause":
        return F.INCORRECT_ROOT_CAUSE
    return F.MAX_ATTEMPTS if report.status == S.MAX_ATTEMPTS else F.TEST_FAILURE
