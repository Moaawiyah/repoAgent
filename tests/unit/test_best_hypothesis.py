"""Opt-in repair from the best-ranked hypothesis when confidence is not reached."""

from pathlib import Path

from repoagent.benchmark.experiment import ABLATIONS
from repoagent.domain.features import RepairFeatures
from repoagent.domain.repair_execution import ExecutionStatus
from tests.support.execution_provider import ExecutionProvider, run_repair
from tests.support.sandbox import FakeSandboxRunner, execution, pytest_result

AUTH = Path(__file__).resolve().parents[1] / "fixtures/auth_bug"
GREEN = execution(pytest_result(passed=3))


def test_unconfident_investigation_stops_by_default(tmp_path):
    runner = FakeSandboxRunner(attempts=[GREEN])
    report = run_repair(tmp_path, AUTH, runner, ExecutionProvider(weak=True))
    assert report.status is ExecutionStatus.INSUFFICIENT_EVIDENCE
    assert report.attempts == []


def test_best_hypothesis_flag_lets_validation_judge_the_patch(tmp_path):
    runner = FakeSandboxRunner(attempts=[GREEN])
    features = ABLATIONS["best_hypothesis"]
    assert features == RepairFeatures(require_confident_root_cause=False)
    assert features.name == "best_hypothesis"
    report = run_repair(
        tmp_path, AUTH, runner, ExecutionProvider(weak=True), features=features
    )
    assert report.status is ExecutionStatus.VALIDATED
    assert report.investigation.termination_reason != "confident_root_cause"
    assert len(report.attempts) == 1
