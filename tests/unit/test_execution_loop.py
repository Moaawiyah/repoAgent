"""M7 repair loop routing with a fake sandbox and deterministic provider."""

import json
from pathlib import Path

from repoagent import ExecutionStatus
from repoagent.domain.sandbox import SandboxOutcome
from tests.support.execution_provider import (
    DIFF2,
    ExecutionProvider,
    run_repair,
)
from tests.support.repair_provider import DIFF
from tests.support.sandbox import FakeSandboxRunner, execution, pytest_result

ROOT = Path(__file__).resolve().parents[1] / "fixtures/auth_bug"
FAILING = execution(pytest_result(passed=2, failed=["tests/test_login.py::test_upper"]))
PASSING = execution(pytest_result(passed=3))


def test_first_patch_passes_without_failure_analysis(tmp_path):
    runner = FakeSandboxRunner(attempts=[PASSING])
    provider = ExecutionProvider()
    report = run_repair(tmp_path, ROOT, runner, provider)
    assert report.status == ExecutionStatus.VALIDATED and report.error is None
    assert len(report.attempts) == 1 and report.attempts[0].validation.passed
    assert not provider.prompts("failure_analysis")
    assert runner.runs[0][1] is None and runner.runs[1][1] == DIFF
    assert runner.opened == runner.closed == 1
    metrics = report.metrics
    assert metrics.attempts == 1 and metrics.llm_calls == len(provider.requests)
    assert metrics.files_changed == 1 and metrics.lines_changed == 2
    assert metrics.tests_before["passed"] == 1 and metrics.tests_after["passed"] == 3
    assert metrics.retrieval_calls > 0 and metrics.final_status == "validated"
    [stored] = (tmp_path / "data/repairs").glob("*.json")
    assert json.loads(stored.read_text())["status"] == "validated"


def test_failure_is_analyzed_revised_and_then_validated(tmp_path):
    runner = FakeSandboxRunner(attempts=[FAILING, PASSING])
    provider = ExecutionProvider()
    report = run_repair(tmp_path, ROOT, runner, provider, max_attempts=3)
    assert report.status == ExecutionStatus.VALIDATED
    first, second = report.attempts
    assert first.failure_analysis.source == "llm"
    assert "secondary lookup" in first.failure_analysis.likely_reason
    assert first.proposal.unified_diff == DIFF and second.proposal.unified_diff == DIFF2
    assert len(provider.prompts("failure_analysis")) == 1
    revision = json.loads(provider.prompts("patch_proposal")[1].user)["untrusted_data"]
    feedback = revision["runtime_validation_feedback"]
    assert feedback["attempt"] == 1 and feedback["failed_tests"][0]["test_id"]
    analyzer = json.loads(provider.prompts("failure_analysis")[0].user)
    assert len(analyzer["untrusted_data"]["validation"]["output_tail"]) <= 2000


def test_max_attempts_bounds_the_loop(tmp_path):
    runner = FakeSandboxRunner(attempts=[FAILING, FAILING])
    provider = ExecutionProvider()
    report = run_repair(tmp_path, ROOT, runner, provider, max_attempts=2)
    assert report.status == ExecutionStatus.MAX_ATTEMPTS
    assert len(report.attempts) == 2 and len(runner.runs) == 3
    assert len(provider.prompts("failure_analysis")) == 1
    assert all(a.failure_summary for a in report.attempts)


def test_patch_apply_failure_is_structured_and_terminal(tmp_path):
    failed = execution(
        outcome=SandboxOutcome.PATCH_APPLY_FAILED, errors=["context mismatch"]
    )
    report = run_repair(
        tmp_path, ROOT, FakeSandboxRunner(attempts=[failed]), ExecutionProvider()
    )
    assert report.status == ExecutionStatus.PATCH_APPLY_FAILED
    assert "context mismatch" in report.attempts[0].validation.summary


def test_timeout_stops_without_llm_analysis(tmp_path):
    timed = execution(
        pytest_result(exit_code=None, timed_out=True), outcome=SandboxOutcome.TIMEOUT
    )
    provider = ExecutionProvider()
    report = run_repair(tmp_path, ROOT, FakeSandboxRunner(attempts=[timed]), provider)
    assert report.status == ExecutionStatus.TIMEOUT
    assert report.attempts[0].failure_analysis.category == "timeout"
    assert not provider.prompts("failure_analysis")


def test_sandbox_unavailable_spends_no_llm_calls(tmp_path):
    provider = ExecutionProvider()
    runner = FakeSandboxRunner(fail_open="Docker daemon is unavailable")
    report = run_repair(tmp_path, ROOT, runner, provider)
    assert report.status == ExecutionStatus.SANDBOX_FAILED
    assert report.investigation is None and not provider.requests
    assert report.metrics.llm_calls == 0 and "Docker" in report.error


def test_sandbox_error_during_baseline(tmp_path):
    broken = execution(outcome=SandboxOutcome.SANDBOX_ERROR, errors=["exit 125"])
    provider = ExecutionProvider()
    report = run_repair(tmp_path, ROOT, FakeSandboxRunner(baseline=broken), provider)
    assert report.status == ExecutionStatus.SANDBOX_FAILED
    assert not provider.prompts("patch_proposal") and not report.attempts


def test_repository_change_is_never_validated(tmp_path):
    changed = execution(pytest_result(passed=3), unchanged=False)
    runner = FakeSandboxRunner(attempts=[changed])
    report = run_repair(tmp_path, ROOT, runner, ExecutionProvider())
    assert report.status == ExecutionStatus.SANDBOX_FAILED
    assert not report.attempts[0].validation.passed
