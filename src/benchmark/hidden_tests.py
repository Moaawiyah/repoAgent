"""Evaluator-only hidden-test check, run after the agent has finished."""

from pathlib import Path

from repoagent.benchmark.models import BenchmarkTask
from repoagent.config import Settings
from repoagent.domain.repair_execution import ExecutionStatus, ValidatedRepairReport
from repoagent.domain.sandbox import CommandKind, CommandSpec, SandboxOutcome
from repoagent.ports.sandbox import SandboxRunner
from repoagent.sdk.validated_repair import sandbox_limits
from repoagent.validation.detection import ProjectDetector
from repoagent.validation.evaluator import ValidationEvaluator


class HiddenTestEvaluator:
    """Applies the agent's final patch plus hidden tests in a fresh sandbox."""

    def __init__(self, settings: Settings, sandbox: SandboxRunner | None) -> None:
        self._settings, self._sandbox = settings, sandbox

    def evaluate(
        self,
        task: BenchmarkTask,
        path: Path,
        report: ValidatedRepairReport,
        timeout: int,
    ) -> bool | None:
        """``None`` when no hidden tests apply; otherwise whether pytest passed."""
        hidden = task.validation.hidden_tests
        proposal = report.final_proposal
        if (
            not hidden
            or report.status != ExecutionStatus.VALIDATED
            or self._sandbox is None
            or proposal is None
        ):
            return None
        limits = sandbox_limits(self._settings, timeout)
        pytest = CommandSpec(kind=CommandKind.PYTEST)
        plan = ProjectDetector(limits).detect(path)
        plan = plan.model_copy(update={"commands": [pytest]})
        with self._sandbox.session(path, plan, limits) as session:
            execution = session.run([pytest], proposal.unified_diff, hidden)
        if execution.outcome != SandboxOutcome.COMPLETED:
            return False
        return ValidationEvaluator().patched(execution, None).passed
