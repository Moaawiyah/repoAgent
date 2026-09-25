"""Benchmark runner: materialize, index, evaluate, execute, persist each task."""

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from repoagent.benchmark.experiment import ExperimentConfig
from repoagent.benchmark.gold import expected_symbols
from repoagent.benchmark.materialize import RepositoryMaterializer
from repoagent.benchmark.metrics import BenchmarkSummary, summarize
from repoagent.benchmark.models import BenchmarkSuite, BenchmarkTask
from repoagent.benchmark.provenance import RunManifest
from repoagent.benchmark.results import FailureCategory, TaskResult
from repoagent.benchmark.store import JsonlResultStore
from repoagent.benchmark.task_executor import TaskExecutor
from repoagent.domain.errors import LLMError, RepoAgentError

LOGGER = logging.getLogger(__name__)
Progress = Callable[[TaskResult], None]

if TYPE_CHECKING:
    from repoagent.sdk import RepoAgent


def _failure(category: FailureCategory, error: Exception) -> dict:
    status = (
        "provider_error"
        if category == FailureCategory.PROVIDER_ERROR
        else "setup_failed"
    )
    return {
        "status": status,
        "failure_category": category,
        "failure_reason": f"{type(error).__name__}: {str(error)[:400]}",
    }


class BenchmarkRunner:
    """Every task/experiment pair yields exactly one persisted result."""

    def __init__(
        self,
        client: "RepoAgent",
        executor: TaskExecutor,
        materializer: RepositoryMaterializer,
        store: JsonlResultStore,
    ) -> None:
        self._client, self._executor = client, executor
        self._materializer, self._store = materializer, store

    def run(
        self,
        suite: BenchmarkSuite,
        manifest: RunManifest,
        progress: Progress | None = None,
    ) -> tuple[RunManifest, BenchmarkSummary]:
        self._store.start(manifest)
        results = []
        for task in suite.select(manifest.task_ids):
            for result in self._task(task, manifest):
                self._store.append(result)
                results.append(result)
                if progress:
                    progress(result)
        manifest = manifest.model_copy(update={"finished_at": datetime.now(UTC)})
        summary = summarize(manifest.run_id, suite.name, results)
        self._store.finish(manifest, summary.model_dump_json(indent=2))
        return manifest, summary

    def _task(self, task: BenchmarkTask, manifest: RunManifest) -> list[TaskResult]:
        start = time.monotonic()
        try:
            path = self._materializer.materialize(task.repository)
            self._client.index(path)
            if task.gold_patch and not task.expected_symbols:
                labels = expected_symbols(task.gold_patch, self._client.analyze(path))
                task = task.model_copy(update={"expected_symbols": labels})
        except (RepoAgentError, OSError) as error:
            fields = _failure(FailureCategory.SETUP_FAILURE, error)
            return [
                self._result(task, manifest, config, start, fields)
                for config in manifest.experiments
            ]
        setup = time.monotonic() - start
        return [
            self._experiment(task, path, manifest, config, setup)
            for config in manifest.experiments
        ]

    def _experiment(
        self,
        task: BenchmarkTask,
        path: Path,
        manifest: RunManifest,
        config: ExperimentConfig,
        setup: float,
    ) -> TaskResult:
        start = time.monotonic() - setup
        LOGGER.info(
            "Benchmark task",
            extra={"event": "benchmark_task", "task_id": task.task_id},
        )
        try:
            fields = self._executor.retrieval(task, path, config)
            fields |= self._executor.execute(task, path, config)
        except LLMError as error:
            fields = _failure(FailureCategory.PROVIDER_ERROR, error)
        except RepoAgentError as error:
            fields = _failure(FailureCategory.SETUP_FAILURE, error)
        return self._result(task, manifest, config, start, fields)

    @staticmethod
    def _result(
        task: BenchmarkTask,
        manifest: RunManifest,
        config: ExperimentConfig,
        start: float,
        fields: dict,
    ) -> TaskResult:
        return TaskResult(
            run_id=manifest.run_id,
            task_id=task.task_id,
            benchmark=task.benchmark,
            experiment=config.name,
            mode=config.mode.value,
            k=config.k,
            repository_commit=task.repository.commit,
            duration_seconds=round(time.monotonic() - start, 3),
            **fields,
        )
