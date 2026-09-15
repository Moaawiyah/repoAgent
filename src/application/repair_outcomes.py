"""Validated-repair reports for runs that end before the repair loop starts."""

from repoagent.agent.metrics_support import usage_fields
from repoagent.ai.counting import CountingProvider
from repoagent.domain.investigation import InvestigationReport, TerminationReason
from repoagent.domain.repair_execution import (
    ExecutionStatus,
    RepairMetrics,
    ValidatedRepairReport,
)
from repoagent.domain.sandbox import ValidationPlan


def early_report(
    task_id: str,
    repository: str,
    plan: ValidationPlan,
    provider: CountingProvider,
    investigation: InvestigationReport | None,
    sandbox_error: str | None = None,
) -> ValidatedRepairReport:
    if sandbox_error is not None:
        status, error = ExecutionStatus.SANDBOX_FAILED, sandbox_error
    elif investigation is None:
        status = ExecutionStatus.VALIDATION_UNAVAILABLE
        error = "No runnable pytest validation was detected; cannot validate."
    elif investigation.termination_reason == TerminationReason.PROVIDER_ERROR:
        status = ExecutionStatus.PROVIDER_ERROR
        error = investigation.error or "Investigator provider failed"
    else:
        status = ExecutionStatus.INSUFFICIENT_EVIDENCE
        error = "No patch proposed because investigation lacks a confident root cause."
    return ValidatedRepairReport(
        task_id=task_id,
        repository=repository,
        status=status,
        investigation=investigation,
        plan=plan,
        metrics=RepairMetrics(
            **usage_fields(provider),
            retrieval_calls=investigation.tool_calls if investigation else 0,
            investigations=int(investigation is not None),
            final_status=status,
        ),
        error=error[:1000],
    )
