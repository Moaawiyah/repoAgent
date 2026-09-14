"""Human-readable presentation of M7 validated repair reports."""

from repoagent.domain.repair_execution import (
    ExecutionStatus,
    RepairAttempt,
    ValidatedRepairReport,
)
from repoagent.domain.validation import ValidationResult

OK, FAIL, ARROW = "✓", "✗", "→"


def _tests(result: ValidationResult) -> str:
    tests = result.tests
    if tests is None or not tests.parsed:
        return f"{FAIL} tests unavailable ({result.execution.outcome.value})"
    if tests.exit_code == 0:
        return f"{OK} tests passed ({tests.passed} passed, {tests.skipped} skipped)"
    return f"{FAIL} {tests.failed} tests failed, {tests.errors} errors"


def _attempt(attempt: RepairAttempt) -> list[str]:
    lines = [f"Attempt {attempt.number}"]
    review = attempt.reviews[-1] if attempt.reviews else None
    lines.append(f"  Developer {OK} patch generated: {attempt.proposal.plan.summary}")
    if review:
        lines.append(f"  Reviewer {OK} {review.decision.value}")
    validation = attempt.validation
    if validation.execution.outcome.value != "completed":
        lines.append(f"  {FAIL} {validation.summary}")
        return lines
    lines.append(f"  {_tests(validation)}")
    if validation.lint is not None:
        new = validation.comparison.new_lint if validation.comparison else []
        mark = FAIL if new else OK
        lines.append(f"  {mark} lint {'failed' if new else 'passed'}")
    analysis = attempt.failure_analysis
    if analysis:
        lines.append(f"  Failure Analyzer {ARROW} {analysis.likely_reason}")
    return lines


def render_validated_repair(report: ValidatedRepairReport) -> str:
    lines = ["RepoAgent Validated Repair", "", "Investigation"]
    investigation = report.investigation
    root = investigation.primary_hypothesis if investigation else None
    if root:
        lines.append(f"{OK} root cause localized: {root.statement}")
    else:
        lines.append(f"{FAIL} root cause not localized")
    if report.baseline is not None:
        sandbox_ok = report.baseline.execution.outcome.value != "sandbox_error"
        lines += ["Sandbox", f"{OK if sandbox_ok else FAIL} created"]
        lines += ["Baseline", _tests(report.baseline)]
    for attempt in report.attempts:
        lines.extend(_attempt(attempt))
    if report.reinvestigations:
        lines.append(f"Re-investigations: {report.reinvestigations}")
    metrics = report.metrics
    lines += [
        "",
        f"Metrics: attempts={metrics.attempts} llm_calls={metrics.llm_calls} "
        f"retrieval_calls={metrics.retrieval_calls} "
        f"sandbox_seconds={metrics.sandbox_seconds}",
        "Result:",
        report.status.value.upper(),
    ]
    if report.error and report.status != ExecutionStatus.VALIDATED:
        lines.append(report.error)
    lines.append("The original repository was not modified.")
    return "\n".join(lines)
