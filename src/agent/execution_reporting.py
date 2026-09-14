"""Final M7 report and measured metrics from terminal loop state."""

from repoagent.agent.execution_state import ExecutionRepairState
from repoagent.ai.counting import CountingProvider
from repoagent.domain.repair_execution import (
    ExecutionStatus,
    RepairMetrics,
    ValidatedRepairReport,
)
from repoagent.domain.validation import TestSummary, ValidationResult


def _counts(tests: TestSummary | None) -> dict[str, int] | None:
    if tests is None or not tests.parsed:
        return None
    return {
        "passed": tests.passed,
        "failed": tests.failed,
        "skipped": tests.skipped,
        "errors": tests.errors,
    }


class ExecutionReporter:
    def __init__(self, provider: CountingProvider) -> None:
        self._provider = provider

    def report(self, state: ExecutionRepairState) -> dict:
        """Never VALIDATED without a passing sandbox validation of the patch."""
        status = state.status or ExecutionStatus.SANDBOX_FAILED
        last = state.attempts[-1] if state.attempts else None
        if status == ExecutionStatus.VALIDATED and not (
            last and last.validation.passed
        ):
            status = ExecutionStatus.SANDBOX_FAILED
        runs: list[ValidationResult] = [
            *([state.baseline] if state.baseline else []),
            *(attempt.validation for attempt in state.attempts),
        ]
        proposal = state.proposal_report.proposal if state.proposal_report else None
        static = last.static_validation if last else None
        metrics = RepairMetrics(
            attempts=len(state.attempts),
            llm_calls=self._provider.calls,
            retrieval_calls=state.retrieval_calls,
            investigations=state.investigations,
            files_changed=len(static.changed_files) if static else 0,
            lines_changed=static.changed_lines if static else 0,
            validation_seconds=round(
                sum(c.duration_seconds for r in runs for c in r.execution.commands), 3
            ),
            sandbox_seconds=round(sum(r.execution.duration_seconds for r in runs), 3),
            tests_before=_counts(state.baseline.tests) if state.baseline else None,
            tests_after=_counts(last.validation.tests) if last else None,
            final_status=status,
        )
        return {
            "report": ValidatedRepairReport(
                task_id=state.task_id,
                repository=state.repository,
                status=status,
                investigation=state.investigation,
                plan=state.plan,
                baseline=state.baseline,
                attempts=state.attempts,
                final_proposal=proposal,
                reviews=state.proposal_report.reviews if state.proposal_report else [],
                reinvestigations=state.reinvestigations,
                metrics=metrics,
                error=(state.error or "")[:1000] or None
                if status != ExecutionStatus.VALIDATED
                else None,
            )
        }
