"""Edge statuses, SDK input validation, and report rendering branches."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from repoagent import ExecutionStatus
from repoagent.cli.execution_render import render_validated_repair
from repoagent.domain.errors import LLMError
from repoagent.domain.sandbox import SandboxOutcome
from tests.support.execution_provider import ExecutionProvider, analysis, run_repair
from tests.support.sandbox import (
    FakeSandboxRunner,
    execution,
    pytest_result,
    ruff_result,
)

ROOT = Path(__file__).resolve().parents[1] / "fixtures/auth_bug"
FAILING = execution(pytest_result(failed=["tests/test_login.py::test_upper"]))


class FailingInvestigator(ExecutionProvider):
    def __init__(self, fail_after=0, **kwargs):
        super().__init__(**kwargs)
        self.fail_after, self.analyses_seen = fail_after, 0

    def complete(self, request):
        if request.prompt_name == "issue_analysis":
            self.analyses_seen += 1
            if self.analyses_seen > self.fail_after:
                raise LLMError("provider down")
        return super().complete(request)


def test_investigation_provider_failure_is_provider_error(tmp_path):
    report = run_repair(tmp_path, ROOT, FakeSandboxRunner(), FailingInvestigator())
    assert report.status == ExecutionStatus.PROVIDER_ERROR
    assert report.metrics.investigations == 1


def test_reinvestigation_provider_failure_is_bounded(tmp_path):
    provider = FailingInvestigator(fail_after=1, analyses=[analysis(uncertain=True)])
    runner = FakeSandboxRunner(attempts=[FAILING])
    report = run_repair(tmp_path, ROOT, runner, provider)
    assert report.status == ExecutionStatus.PROVIDER_ERROR
    assert report.reinvestigations == 1 and len(report.attempts) == 1


def test_reinvestigation_without_confident_root_cause(tmp_path):
    provider = ExecutionProvider(analyses=[analysis(uncertain=True)])
    runner = FakeSandboxRunner(attempts=[FAILING])
    original = provider.complete

    def weaken(request):
        if request.prompt_name == "issue_analysis" and provider.requests:
            provider.weak = True
        return original(request)

    provider.complete = weaken
    report = run_repair(tmp_path, ROOT, runner, provider)
    assert report.status == ExecutionStatus.INSUFFICIENT_EVIDENCE
    assert "Re-investigation" in report.error


def test_zero_attempts_is_rejected_by_sdk(tmp_path):
    with pytest.raises(ValidationError):
        run_repair(
            tmp_path, ROOT, FakeSandboxRunner(), ExecutionProvider(), max_attempts=0
        )


def test_render_covers_failures_lint_and_errors(tmp_path):
    lint = execution(pytest_result(passed=3), ruff_result([("F841", "unused")]))
    timed = execution(outcome=SandboxOutcome.TIMEOUT)
    runner = FakeSandboxRunner(
        baseline=execution(pytest_result(), ruff_result()), attempts=[lint, timed]
    )
    report = run_repair(tmp_path, ROOT, runner, ExecutionProvider())
    text = render_validated_repair(report)
    assert "lint failed" in text and "timeout" in text and "TIMEOUT" in text
    assert "tests unavailable" not in text.split("Attempt 2")[0]
    assert report.attempts[0].failure_analysis.category == "lint"
    unavailable = run_repair(
        tmp_path, ROOT, FakeSandboxRunner(fail_open="no docker"), ExecutionProvider()
    )
    assert "root cause not localized" in render_validated_repair(unavailable)
