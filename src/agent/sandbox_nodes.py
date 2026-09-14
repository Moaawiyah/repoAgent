"""Baseline and patched sandbox execution nodes; purely deterministic."""

import logging

from repoagent.agent.execution_state import ExecutionRepairState
from repoagent.agent.failure_triage import failure_summary, triage
from repoagent.domain.repair_execution import ExecutionStatus, RepairAttempt
from repoagent.domain.sandbox import SandboxOutcome
from repoagent.ports.sandbox import SandboxSession
from repoagent.validation.evaluator import ValidationEvaluator, baseline_usable

LOGGER = logging.getLogger(__name__)
_TERMINAL_OUTCOMES = {
    SandboxOutcome.PATCH_APPLY_FAILED: ExecutionStatus.PATCH_APPLY_FAILED,
    SandboxOutcome.SANDBOX_ERROR: ExecutionStatus.SANDBOX_FAILED,
    SandboxOutcome.TIMEOUT: ExecutionStatus.TIMEOUT,
}


class SandboxNodes:
    def __init__(self, session: SandboxSession) -> None:
        self._session, self._evaluator = session, ValidationEvaluator()

    def baseline(self, state: ExecutionRepairState) -> dict:
        """Validate the unpatched copy so pre-existing failures are known."""
        execution = self._session.run(state.plan.commands, None)
        result = self._evaluator.baseline(execution)
        update: dict = {"baseline": result}
        if not execution.repository_unchanged:
            update |= {"status": ExecutionStatus.SANDBOX_FAILED}
            update["error"] = "Original repository changed during validation"
        elif execution.outcome == SandboxOutcome.SANDBOX_ERROR:
            update |= {"status": ExecutionStatus.SANDBOX_FAILED}
            update["error"] = "; ".join(execution.errors)[:1000] or "Sandbox error"
        elif not baseline_usable(result, state.plan):
            update |= {"status": ExecutionStatus.BASELINE_FAILED}
            update["error"] = f"Baseline validation unusable: {result.summary}"[:1000]
        self._log("baseline_validated", update.get("status"), state.task_id)
        return update

    def execute(self, state: ExecutionRepairState) -> dict:
        """Apply the approved patch to a fresh copy and validate it."""
        report = state.proposal_report
        proposal = report.proposal if report else None
        if report is None or proposal is None or report.validation is None:
            return {"status": ExecutionStatus.SANDBOX_FAILED, "error": "No patch"}
        if any(
            a.proposal.unified_diff == proposal.unified_diff for a in state.attempts
        ):
            return {
                "status": ExecutionStatus.VALIDATION_FAILED,
                "error": "Developer repeated a patch that already failed validation",
            }
        execution = self._session.run(state.plan.commands, proposal.unified_diff)
        validation = self._evaluator.patched(execution, state.baseline)
        attempt = RepairAttempt(
            number=len(state.attempts) + 1,
            proposal=proposal,
            static_validation=report.validation,
            reviews=report.reviews,
            validation=validation,
        )
        update: dict = {}
        if not execution.repository_unchanged:
            update = {"status": ExecutionStatus.SANDBOX_FAILED}
            update["error"] = "Original repository changed during validation"
        elif validation.passed:
            update = {"status": ExecutionStatus.VALIDATED}
        else:
            attempt = self._failed(attempt, state)
            status = _TERMINAL_OUTCOMES.get(execution.outcome)
            if status is None and attempt.number >= state.limits.max_attempts:
                status = ExecutionStatus.MAX_ATTEMPTS
            if status is not None:
                update = {"status": status, "error": attempt.failure_summary}
        self._log("attempt_validated", update.get("status"), state.task_id)
        return update | {"attempts": [*state.attempts, attempt]}

    @staticmethod
    def _failed(attempt: RepairAttempt, state: ExecutionRepairState) -> RepairAttempt:
        validation = attempt.validation
        return attempt.model_copy(
            update={
                "failure_summary": failure_summary(validation),
                "failure_analysis": triage(validation, state.baseline, state.attempts),
            }
        )

    @staticmethod
    def _log(event: str, status: ExecutionStatus | None, task_id: str) -> None:
        LOGGER.info(
            event,
            extra={"event": event, "task_id": task_id, "status": status or "running"},
        )
