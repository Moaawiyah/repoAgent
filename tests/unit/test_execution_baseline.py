"""Baseline comparison, regressions, re-investigation and stop conditions."""

from pathlib import Path

from repoagent import ExecutionStatus
from tests.support.execution_provider import ExecutionProvider, analysis, run_repair
from tests.support.repair_provider import DIFF
from tests.support.sandbox import FakeSandboxRunner, execution, pytest_result

ROOT = Path(__file__).resolve().parents[1] / "fixtures/auth_bug"
UPPER, OTHER = "tests/test_login.py::test_upper", "tests/test_login.py::test_other"
BASELINE_RED = execution(pytest_result(passed=2, failed=[UPPER]))


def test_pre_existing_failure_fixed_by_patch_is_validated(tmp_path):
    runner = FakeSandboxRunner(BASELINE_RED, [execution(pytest_result(passed=3))])
    report = run_repair(tmp_path, ROOT, runner, ExecutionProvider())
    assert report.status == ExecutionStatus.VALIDATED
    assert report.baseline.tests.failing_ids == {UPPER}
    assert report.attempts[0].validation.comparison.fixed_failures == [UPPER]
    assert report.metrics.tests_before["failed"] == 1


def test_unusable_baseline_stops_before_developer(tmp_path):
    usage_error = execution(pytest_result(exit_code=4))
    provider = ExecutionProvider()
    report = run_repair(tmp_path, ROOT, FakeSandboxRunner(usage_error), provider)
    assert report.status == ExecutionStatus.BASELINE_FAILED
    assert not provider.prompts("patch_proposal") and report.baseline is not None


def test_regression_is_detected_and_attributed_to_patch(tmp_path):
    regressed = execution(pytest_result(passed=2, failed=[OTHER]))
    runner = FakeSandboxRunner(BASELINE_RED, [regressed])
    provider = ExecutionProvider(analyses=[analysis("stop", caused=False)])
    report = run_repair(tmp_path, ROOT, runner, provider)
    comparison = report.attempts[0].validation.comparison
    assert comparison.new_failures == [OTHER] and comparison.regression
    assert comparison.fixed_failures == [UPPER]
    assert report.attempts[0].failure_analysis.patch_caused_failure is True
    assert report.status == ExecutionStatus.VALIDATION_FAILED


def test_uncertain_root_cause_reenters_investigation_once(tmp_path):
    failing = execution(pytest_result(passed=2, failed=[UPPER]))
    runner = FakeSandboxRunner(
        attempts=[failing, failing, execution(pytest_result(passed=3))]
    )
    provider = ExecutionProvider(analyses=[analysis(uncertain=True)])
    report = run_repair(tmp_path, ROOT, runner, provider, max_attempts=3)
    assert report.status == ExecutionStatus.VALIDATED
    assert report.reinvestigations == 1 and report.metrics.investigations == 2
    assert report.attempts[0].failure_analysis.next_action == "reinvestigate"
    observed = report.investigation.issue.observed_behavior
    assert "failed sandbox validation" in observed
    assert len(provider.prompts("issue_analysis")) == 2


def test_ordinary_failure_does_not_reinvestigate(tmp_path):
    runner = FakeSandboxRunner(
        attempts=[execution(pytest_result(failed=[UPPER])), execution(pytest_result())]
    )
    provider = ExecutionProvider(analyses=[analysis()])
    report = run_repair(tmp_path, ROOT, runner, provider)
    assert report.status == ExecutionStatus.VALIDATED
    assert report.reinvestigations == 0
    assert len(provider.prompts("issue_analysis")) == 1


def test_repeated_identical_patch_stops(tmp_path):
    runner = FakeSandboxRunner(attempts=[execution(pytest_result(failed=[UPPER]))])
    provider = ExecutionProvider(patches=(DIFF,))
    report = run_repair(tmp_path, ROOT, runner, provider, max_attempts=3)
    assert report.status == ExecutionStatus.VALIDATION_FAILED
    assert len(report.attempts) == 1 and "repeated" in report.error


def test_duplicate_failure_reuses_analysis_without_llm(tmp_path):
    same = execution(pytest_result(failed=[UPPER]))
    runner = FakeSandboxRunner(attempts=[same, same, execution(pytest_result())])
    provider = ExecutionProvider()
    report = run_repair(tmp_path, ROOT, runner, provider, max_attempts=3)
    assert report.status == ExecutionStatus.VALIDATED
    assert len(provider.prompts("failure_analysis")) == 1
    second = report.attempts[1].failure_analysis
    assert second.source == "deterministic" and "Identical" in second.likely_reason


def test_review_rejection_never_executes_patch(tmp_path):
    runner = FakeSandboxRunner()
    report = run_repair(
        tmp_path, ROOT, runner, ExecutionProvider(decisions=("reject",))
    )
    assert report.status == ExecutionStatus.REVIEW_REJECTED
    assert len(runner.runs) == 1 and not report.attempts


def test_insufficient_investigation_is_reported(tmp_path):
    runner = FakeSandboxRunner()
    report = run_repair(tmp_path, ROOT, runner, ExecutionProvider(rounds=10))
    assert report.status == ExecutionStatus.INSUFFICIENT_EVIDENCE
    assert not runner.runs and report.final_proposal is None
