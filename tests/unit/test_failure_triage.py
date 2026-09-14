"""Deterministic triage, focused analyzer context, and analyzer failures."""

import json
from pathlib import Path

from repoagent import ExecutionStatus
from repoagent.agent.failure_triage import failure_summary, triage
from repoagent.agent.runtime_feedback import reinvestigation_issue
from repoagent.domain.investigation import Issue
from repoagent.domain.repair_execution import FailureAnalysis
from repoagent.validation.evaluator import ValidationEvaluator
from tests.support.execution_provider import ExecutionProvider, run_repair
from tests.support.sandbox import (
    FakeSandboxRunner,
    execution,
    pytest_result,
    ruff_result,
)

ROOT = Path(__file__).resolve().parents[1] / "fixtures/auth_bug"
EVALUATOR = ValidationEvaluator()


def patched(*commands, baseline=None):
    return EVALUATOR.patched(execution(*commands), baseline)


def test_lint_only_failure_needs_no_model():
    baseline = EVALUATOR.baseline(execution(pytest_result(), ruff_result()))
    result = patched(
        pytest_result(), ruff_result([("F841", "unused variable")]), baseline=baseline
    )
    analysis = triage(result, baseline, [])
    assert analysis.category == "lint" and analysis.patch_caused_failure
    assert analysis.next_action == "revise_patch" and analysis.affected_file


def test_new_collection_error_needs_no_model():
    baseline = EVALUATOR.baseline(execution(pytest_result()))
    result = patched(pytest_result(errors=["tests/test_a.py"], exit_code=2))
    analysis = triage(result, baseline, [])
    assert analysis.category == "collection_error"
    assert analysis.affected_file == "tests/test_a.py"
    assert "ModuleNotFoundError" in analysis.likely_reason


def test_ordinary_test_failure_requires_reasoning():
    baseline = EVALUATOR.baseline(execution(pytest_result()))
    result = patched(pytest_result(failed=["t.py::a"]), baseline=baseline)
    assert triage(result, baseline, []) is None
    assert "t.py::a" in failure_summary(result)


def test_reinvestigation_issue_keeps_original_and_adds_observation():
    analysis = FailureAnalysis(
        category="wrong_root_cause",
        likely_reason="lookup happens in the controller",
        patch_caused_failure=False,
        next_action="reinvestigate",
        evidence_needed=["controller normalization"],
    )
    issue = reinvestigation_issue(Issue(description="bug", title="t"), analysis)
    assert issue.description == "bug" and issue.title == "t"
    assert "controller normalization" in issue.observed_behavior


def test_invalid_analyzer_output_is_provider_error(tmp_path):
    runner = FakeSandboxRunner(attempts=[execution(pytest_result(failed=["t::a"]))])
    provider = ExecutionProvider(analyses=[{"category": "nonsense"}])
    report = run_repair(tmp_path, ROOT, runner, provider)
    assert report.status == ExecutionStatus.PROVIDER_ERROR
    assert report.attempts and report.attempts[0].failure_analysis is None


def test_analyzer_context_is_focused_and_bounded(tmp_path):
    noisy = pytest_result(failed=["t::a"])
    noisy = noisy.model_copy(update={"stdout": "x" * 50000 + "\n" + noisy.stdout})
    runner = FakeSandboxRunner(attempts=[execution(noisy), execution(pytest_result())])
    provider = ExecutionProvider()
    run_repair(tmp_path, ROOT, runner, provider)
    request = provider.prompts("failure_analysis")[0]
    payload = json.loads(request.user)["untrusted_data"]
    assert len(request.user) < 12000 and len(payload["evidence"]) <= 4
    assert set(payload) == {
        "issue",
        "root_cause",
        "patch",
        "evidence",
        "validation",
        "previous_attempts",
    }
