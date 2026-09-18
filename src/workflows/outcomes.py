"""Map final repair reports onto stage outcomes (truthful, never upgraded)."""

from repoagent.domain.repair import RepairReport, RepairStatus
from repoagent.domain.repair_execution import ExecutionStatus, ValidatedRepairReport
from repoagent.domain.workflow import StageStatus

CURRENT = "*"  # the stage that was running when the workflow stopped

_EXECUTION = {
    ExecutionStatus.INSUFFICIENT_EVIDENCE: "investigator",
    ExecutionStatus.REVIEW_REJECTED: "reviewer",
    ExecutionStatus.VALIDATION_FAILED: "docker_validation",
    ExecutionStatus.MAX_ATTEMPTS: "docker_validation",
    ExecutionStatus.PATCH_APPLY_FAILED: "docker_validation",
    ExecutionStatus.SANDBOX_FAILED: "docker_validation",
    ExecutionStatus.TIMEOUT: "docker_validation",
    ExecutionStatus.BASELINE_FAILED: "docker_validation",
    ExecutionStatus.VALIDATION_UNAVAILABLE: "docker_validation",
    ExecutionStatus.PROVIDER_ERROR: CURRENT,
}
_STATIC = {
    RepairStatus.INSUFFICIENT_INVESTIGATION: "investigator",
    RepairStatus.REJECTED: "reviewer",
    RepairStatus.MAX_REVISIONS: "reviewer",
    RepairStatus.PROVIDER_ERROR: CURRENT,
}

Outcome = tuple[str, StageStatus, str]


def repair_outcomes(report: ValidatedRepairReport | RepairReport) -> list[Outcome]:
    """Stage updates implied by the final report's status."""
    if isinstance(report, ValidatedRepairReport):
        detail = report.error or report.status.value.replace("_", " ")
        key = _EXECUTION.get(report.status)
        if key is None:
            last = report.attempts[-1].validation.summary if report.attempts else ""
            return [("docker_validation", StageStatus.DONE, last)]
        return [(key, StageStatus.FAILED, detail)]
    detail = report.error or report.status.value.replace("_", " ")
    key = _STATIC.get(report.status)
    if key is not None:
        return [(key, StageStatus.FAILED, detail)]
    return [
        (
            "docker_validation",
            StageStatus.SKIPPED,
            "Sandbox validation is not enabled for this repository",
        )
    ]
