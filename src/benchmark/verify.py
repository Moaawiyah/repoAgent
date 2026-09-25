"""Verify repair tasks in their pinned sandbox before trusting them (no LLM).

A task is usable only if, in its own environment: the visible suite passes
on the buggy commit (M7 requires a green suite to validate), the hidden
tests fail on the buggy code, and the gold patch plus hidden tests pass.
"""

import time
from pathlib import Path

from repoagent.analysis.models import AnalysisModel
from repoagent.benchmark.environment import image_digest, task_runner, task_settings
from repoagent.benchmark.models import BenchmarkTask
from repoagent.config import Settings
from repoagent.domain.errors import SandboxError
from repoagent.domain.sandbox import CommandKind, CommandSpec, SandboxExecution
from repoagent.ports.sandbox import SandboxRunner
from repoagent.sdk.validated_repair import sandbox_limits
from repoagent.validation.detection import ProjectDetector
from repoagent.validation.evaluator import ValidationEvaluator

PYTEST = CommandSpec(kind=CommandKind.PYTEST)


class TaskCheck(AnalysisModel):
    task_id: str
    verified: bool = False
    visible_passes: bool | None = None
    hidden_fails_on_buggy: bool | None = None
    gold_passes: bool | None = None
    reason: str | None = None
    image: str | None = None
    image_digest: str | None = None
    duration_seconds: float = 0.0


def _passed(execution: SandboxExecution) -> bool:
    return ValidationEvaluator().patched(execution, None).passed


def _summary(execution: SandboxExecution) -> str:
    output = "\n".join(c.stdout + c.stderr for c in execution.commands)
    tail = [line for line in output.splitlines() if line.strip()][-1:] or [""]
    return f"{execution.outcome.value}: {' '.join(execution.errors)} {tail[0]}"[:300]


def verify_task(
    task: BenchmarkTask,
    path: Path,
    settings: Settings,
    injected: SandboxRunner | None = None,
    timeout: int = 600,
) -> TaskCheck:
    start = time.monotonic()
    settings = task_settings(settings, task)
    check = TaskCheck(
        task_id=task.task_id,
        image=settings.sandbox_image,
        image_digest=image_digest(settings.sandbox_image) if not injected else None,
    )
    hidden = task.validation.hidden_tests
    if not task.gold_patch or not hidden:
        reason = "needs gold patch and hidden tests"
        return check.model_copy(update={"reason": reason})
    limits = sandbox_limits(settings, timeout)
    plan = (
        ProjectDetector(limits).detect(path).model_copy(update={"commands": [PYTEST]})
    )
    fields: dict = {}
    try:
        with task_runner(settings, injected).session(path, plan, limits) as session:
            visible = session.run([PYTEST], None)
            fields["visible_passes"] = _passed(visible)
            buggy = session.run([PYTEST], None, hidden)
            fields["hidden_fails_on_buggy"] = not _passed(buggy)
            gold = session.run([PYTEST], task.gold_patch, hidden)
            fields["gold_passes"] = _passed(gold)
    except SandboxError as error:
        fields["reason"] = f"sandbox: {str(error)[:200]}"
    else:
        failed = [
            (name, execution)
            for name, execution, ok in (
                (
                    "visible suite fails on buggy commit",
                    visible,
                    fields["visible_passes"],
                ),
                (
                    "hidden tests pass on buggy code",
                    buggy,
                    fields["hidden_fails_on_buggy"],
                ),
                ("gold patch + hidden tests fail", gold, fields["gold_passes"]),
            )
            if not ok
        ]
        fields["verified"] = not failed
        if failed:
            name, execution = failed[0]
            fields["reason"] = f"{name} ({_summary(execution)})"
    fields["duration_seconds"] = round(time.monotonic() - start, 1)
    return check.model_copy(update=fields)
