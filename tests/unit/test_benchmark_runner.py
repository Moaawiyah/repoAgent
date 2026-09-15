"""Benchmark execution through the SDK with deterministic test doubles."""

import json
from pathlib import Path

import pytest

from repoagent import RepoAgent, Settings
from repoagent.benchmark.results import FailureCategory
from repoagent.domain.errors import LLMError, StorageError
from tests.support.execution_provider import ExecutionProvider
from tests.support.sandbox import FakeSandboxRunner, execution, pytest_result

ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "benchmarks/fixtures.json"
AUTH = "auth-uppercase-email"
PASSING = execution(pytest_result(passed=3))


def api(tmp_path, runner=None, **settings):
    options = Settings(data_dir=tmp_path / "data", **settings)
    return RepoAgent(settings=options, sandbox_runner=runner).benchmarks()


def test_retrieval_mode_persists_reproducible_results(tmp_path):
    benchmarks = api(tmp_path, llm_api_key="sk-must-not-leak")
    run = benchmarks.run(SUITE, task_ids=[AUTH, "cache-bug"], k=3)
    manifest, summary = run.manifest, run.summary
    assert manifest.task_ids == [AUTH, "cache-bug"] and manifest.finished_at
    assert manifest.repoagent_version and manifest.suite_sha256
    experiment = summary.experiments[0]
    assert experiment.tasks_attempted == 2 and experiment.success_rate is None
    assert set(experiment.retrieval) == {"bm25", "vector", "hybrid", "hybrid_graph"}
    directory = tmp_path / "data/benchmarks/runs" / manifest.run_id
    assert (directory / "summary.json").is_file()
    stored = [json.loads(line) for line in (directory / "results.jsonl").open()]
    assert [r["task_id"] for r in stored] == [AUTH, "cache-bug"]
    assert "sk-must-not-leak" not in (directory / "manifest.json").read_text()
    loaded = benchmarks.load(manifest.run_id)
    assert loaded.summary == summary and len(loaded.results) == 2
    assert benchmarks.runs() == [manifest.run_id]


def test_repair_mode_with_hidden_tests_and_ablations(tmp_path):
    # Per experiment: baseline, patched attempt, then hidden-test evaluation.
    runner = FakeSandboxRunner(attempts=[PASSING] * 5)
    run = api(tmp_path, runner).run(
        SUITE,
        mode="repair",
        ablations=["full", "no_reviewer"],
        task_ids=[AUTH],
        provider=ExecutionProvider(),
    )
    full, no_reviewer = run.summary.experiments
    assert full.validated_repairs == 1 and full.hidden_tests_resolved == 1
    assert full.success_rate == 1.0 and full.avg_attempts == 1.0
    assert full.file_localization == 1.0 and full.lines_added == 1
    assert full.avg_llm_calls > no_reviewer.avg_llm_calls
    hidden = [o for o in runner.overlays if o]
    assert len(hidden) == 2 and "tests/test_hidden_email.py" in hidden[0]
    assert runner.runs[2][1] is not None


def test_hidden_test_failure_is_classified(tmp_path):
    red = execution(pytest_result(failed=["tests/test_hidden_email.py::t"]))
    runner = FakeSandboxRunner(attempts=[PASSING, red])
    run = api(tmp_path, runner).run(
        SUITE, mode="repair", task_ids=[AUTH], provider=ExecutionProvider()
    )
    experiment = run.summary.experiments[0]
    assert experiment.validated_repairs == 1 and experiment.hidden_tests_resolved == 0
    assert experiment.failures == {FailureCategory.TEST_FAILURE.value: 1}


def test_investigate_mode_measures_localization(tmp_path):
    run = api(tmp_path).run(
        SUITE, mode="investigate", task_ids=[AUTH], provider=ExecutionProvider()
    )
    experiment = run.summary.experiments[0]
    assert experiment.localization_measured == 1
    assert experiment.file_localization == 1.0 and experiment.avg_llm_calls > 0


def test_llm_modes_require_provider_before_running(tmp_path):
    with pytest.raises(LLMError):
        api(tmp_path).run(SUITE, mode="investigate")
    assert not (tmp_path / "data/benchmarks/runs").exists()


def test_setup_failures_are_recorded_per_experiment(tmp_path):
    suite = json.loads(SUITE.read_text())
    suite["tasks"] = suite["tasks"][:1]
    suite["tasks"][0]["repository"]["source"] = "missing-repo"
    path = tmp_path / "broken.json"
    path.write_text(json.dumps(suite))
    run = api(tmp_path).run(path)
    result = run.summary.experiments[0]
    assert result.failures == {"setup_failure": 1}
    with pytest.raises(StorageError):
        api(tmp_path).load("../escape")
