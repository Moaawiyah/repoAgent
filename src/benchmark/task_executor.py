"""Execute one benchmark task under one experiment through the public SDK."""

from pathlib import Path
from typing import TYPE_CHECKING

from repoagent.agent.metrics_support import diff_stats
from repoagent.ai.provider import LLMProvider
from repoagent.benchmark.classification import classify_investigation, classify_repair
from repoagent.benchmark.experiment import BenchmarkMode, ExperimentConfig
from repoagent.benchmark.hidden_tests import HiddenTestEvaluator
from repoagent.benchmark.models import BenchmarkTask
from repoagent.benchmark.results import RetrievalScore, TokenUsage
from repoagent.benchmark.scoring import localization, patch_metrics
from repoagent.config import Settings
from repoagent.evaluation.models import RetrievalCase
from repoagent.ports.sandbox import SandboxRunner

if TYPE_CHECKING:
    from repoagent.sdk import RepoAgent


class TaskExecutor:
    """Labels are used only here, after the agent has produced its output."""

    def __init__(
        self,
        client: "RepoAgent",
        settings: Settings,
        sandbox: SandboxRunner | None,
        provider: LLMProvider | None,
    ) -> None:
        self._client, self._settings = client, settings
        self._sandbox, self._provider = sandbox, provider

    def retrieval(
        self, task: BenchmarkTask, path: Path, config: ExperimentConfig
    ) -> dict[str, RetrievalScore]:
        case = RetrievalCase(
            query=task.issue,
            expected_files=task.expected_files,
            expected_symbols=task.expected_symbols,
        )
        report = self._client.evaluate(
            path, [case], k=config.k, strategies=config.strategies
        )
        return {
            row.strategy.value: RetrievalScore(
                recall_at_k=row.recall_at_k, mrr=row.mrr, hit_at_k=row.hit_rate_at_k
            )
            for row in report.rows
        }

    def execute(
        self, task: BenchmarkTask, path: Path, config: ExperimentConfig
    ) -> dict:
        """Return TaskResult fields for the configured mode."""
        if config.mode == BenchmarkMode.RETRIEVAL:
            return {"status": "retrieval_evaluated"}
        if config.mode == BenchmarkMode.INVESTIGATE:
            report = self._client.investigate(
                path,
                task.issue,
                max_iterations=1 if config.features.single_retrieval_pass else None,
                provider=self._provider,
                use_graph=config.features.graph_retrieval,
            )
            located = localization(task, report)
            category = classify_investigation(report, located, task.expected_files)
            usage = report.usage
            return {
                "status": report.termination_reason.value,
                "success": category is None,
                "failure_category": category,
                "failure_reason": report.error,
                "localization": located,
                "retrieval_calls": report.tool_calls,
                "tokens": TokenUsage(
                    llm_calls=usage.llm_calls,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                ),
            }
        return self._repair(task, path, config)

    def _repair(
        self, task: BenchmarkTask, path: Path, config: ExperimentConfig
    ) -> dict:
        report = self._client.repair_and_validate(
            path,
            task.issue,
            max_attempts=config.max_attempts,
            timeout=config.timeout_seconds,
            provider=self._provider,
            features=config.features,
        )
        hidden = HiddenTestEvaluator(self._settings, self._sandbox).evaluate(
            task, path, report, config.timeout_seconds
        )
        located = localization(task, report.investigation)
        category = classify_repair(report, located, task.expected_files, hidden)
        metrics, proposal = report.metrics, report.final_proposal
        added, removed = diff_stats(proposal.unified_diff if proposal else None)
        return {
            "status": report.status.value,
            "success": category is None,
            "failure_category": category,
            "failure_reason": report.error,
            "localization": located,
            "attempts": metrics.attempts,
            "retrieval_calls": metrics.retrieval_calls,
            "patch": patch_metrics(
                task, proposal, (metrics.files_changed, added, removed)
            ),
            "tests_before": metrics.tests_before,
            "tests_after": metrics.tests_after,
            "hidden_tests_passed": hidden,
            "tokens": TokenUsage(
                llm_calls=metrics.llm_calls,
                input_tokens=metrics.input_tokens,
                output_tokens=metrics.output_tokens,
                prompt_chars=metrics.prompt_chars,
            ),
            "sandbox_seconds": metrics.sandbox_seconds,
        }
