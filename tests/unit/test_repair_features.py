"""Ablation feature flags and measured token/prompt accounting."""

from pathlib import Path

from repoagent import ExecutionStatus
from repoagent.agent.metrics_support import diff_stats
from repoagent.ai.provider import CompletionResult, CompletionUsage
from repoagent.domain.features import RepairFeatures
from tests.support.execution_provider import ExecutionProvider, run_repair
from tests.support.repair_provider import DIFF
from tests.support.sandbox import FakeSandboxRunner, execution, pytest_result

ROOT = Path(__file__).resolve().parents[1] / "fixtures/auth_bug"
FAILING = execution(pytest_result(failed=["tests/test_login.py::test_upper"]))
PASSING = execution(pytest_result(passed=3))


class MeteredProvider(ExecutionProvider):
    def complete(self, request):
        result = super().complete(request)
        usage = CompletionUsage(input_tokens=100, output_tokens=10)
        return CompletionResult(text=result.text, model=result.model, usage=usage)


def test_full_pipeline_reports_provider_token_usage(tmp_path):
    provider = MeteredProvider()
    report = run_repair(tmp_path, ROOT, FakeSandboxRunner(attempts=[PASSING]), provider)
    metrics = report.metrics
    assert metrics.llm_calls == len(provider.requests) > 0
    assert metrics.input_tokens == 100 * metrics.llm_calls
    assert metrics.output_tokens == 10 * metrics.llm_calls
    assert metrics.stage_calls["patch_review"] == 1 and metrics.prompt_chars > 0
    assert (metrics.lines_added, metrics.lines_removed) == (1, 1)


def test_no_reviewer_skips_review_llm_call(tmp_path):
    provider = ExecutionProvider()
    features = RepairFeatures(reviewer=False)
    runner = FakeSandboxRunner(attempts=[PASSING])
    report = run_repair(tmp_path, ROOT, runner, provider, features=features)
    assert report.status == ExecutionStatus.VALIDATED
    assert not provider.prompts("patch_review")
    assert "disabled" in report.attempts[0].reviews[0].rationale


def test_no_failure_retry_stops_after_first_attempt(tmp_path):
    provider = ExecutionProvider()
    runner = FakeSandboxRunner(attempts=[FAILING, PASSING])
    features = RepairFeatures(failure_retry=False)
    report = run_repair(tmp_path, ROOT, runner, provider, features=features)
    assert report.status == ExecutionStatus.MAX_ATTEMPTS
    assert len(report.attempts) == 1 and not provider.prompts("failure_analysis")


def test_single_retrieval_pass_and_no_graph(tmp_path):
    provider = ExecutionProvider(rounds=2)
    features = RepairFeatures(single_retrieval_pass=True, graph_retrieval=False)
    runner = FakeSandboxRunner(attempts=[PASSING])
    report = run_repair(tmp_path, ROOT, runner, provider, features=features)
    investigation = report.investigation
    assert investigation.iterations <= 1
    assert all("graph" not in e.retrieval_source for e in investigation.evidence)
    assert features.name == "no_graph+single_pass"
    assert RepairFeatures().name == "full"


def test_diff_stats_ignores_headers():
    assert diff_stats(DIFF) == (1, 1)
    assert diff_stats(None) == (0, 0)
