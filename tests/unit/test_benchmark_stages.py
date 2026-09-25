"""Every failure category maps to a pipeline stage; repair summaries count them."""

from repoagent.benchmark.metrics import summarize_experiment
from repoagent.benchmark.report import _experiment
from repoagent.benchmark.results import FAILURE_STAGES, FailureCategory, TaskResult

STAGES = {
    "retrieval",
    "investigation",
    "provider_schema",
    "patch_generation",
    "reviewer_rejection",
    "sandbox_setup",
    "validation_test",
}


def result(task, **fields):
    base = {"run_id": "r", "benchmark": "b", "experiment": "full", "mode": "repair"}
    return TaskResult(task_id=task, status="x", **base, **fields)


def test_every_category_has_one_of_the_seven_stages():
    assert set(FAILURE_STAGES) == set(FailureCategory)
    assert set(FAILURE_STAGES.values()) == STAGES


def test_repair_summary_counts_stages_first_attempts_and_regressions():
    results = [
        result("a", success=True, attempts=1, hidden_tests_passed=True),
        result("b", success=True, attempts=2, hidden_tests_passed=True),
        result("c", failure_category=FailureCategory.REGRESSION, attempts=3),
        result("d", failure_category=FailureCategory.LOCALIZATION_FAILURE),
        result("e", failure_category=FailureCategory.PROVIDER_ERROR),
    ]
    summary = summarize_experiment("full", results)
    assert summary.first_attempt_successes == 1 and summary.regressions == 1
    assert summary.hidden_test_success_rate == 0.4
    assert summary.failure_stages == {
        "provider_schema": 1,
        "retrieval": 1,
        "validation_test": 1,
    }
    rendered = "\n".join(_experiment(summary))
    assert "First-attempt successes:  1" in rendered
    assert "Stage retrieval: 1" in rendered
