"""Public SDK capability for M8 benchmark runs and stored results."""

from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from repoagent.ai.openai_provider import llm_provider_from_settings
from repoagent.ai.provider import LLMProvider, require_provider
from repoagent.benchmark.experiment import BenchmarkMode, experiments
from repoagent.benchmark.loaders import load_suite, resolve_suite
from repoagent.benchmark.materialize import RepositoryMaterializer
from repoagent.benchmark.metrics import BenchmarkSummary, summarize
from repoagent.benchmark.provenance import RunManifest, build_manifest
from repoagent.benchmark.results import TaskResult
from repoagent.benchmark.runner import BenchmarkRunner
from repoagent.benchmark.store import JsonlResultStore
from repoagent.benchmark.task_executor import TaskExecutor
from repoagent.config import Settings
from repoagent.ports.sandbox import SandboxRunner
from repoagent.sandbox.docker_runner import DockerSandboxRunner


class BenchmarkRun(BaseModel):
    manifest: RunManifest
    summary: BenchmarkSummary
    results: list[TaskResult] = []


class BenchmarkApi:
    def __init__(
        self, settings: Settings, client, runner: SandboxRunner | None
    ) -> None:
        self._settings, self._client, self._runner = settings, client, runner
        self._store = JsonlResultStore(settings.data_dir / "benchmarks" / "runs")

    def run(
        self,
        suite: str | Path,
        *,
        mode: BenchmarkMode | str = BenchmarkMode.RETRIEVAL,
        ablations: list[str] | None = None,
        task_ids: list[str] | None = None,
        k: int = 5,
        max_attempts: int = 3,
        timeout: int | None = None,
        provider: LLMProvider | None = None,
        progress: Callable[[TaskResult], None] | None = None,
    ) -> BenchmarkRun:
        """Run real tasks; LLM modes fail fast when no provider is configured."""
        settings, mode = self._settings, BenchmarkMode(mode)
        path = resolve_suite(str(suite))
        loaded = load_suite(path)
        selected = [task.task_id for task in loaded.select(task_ids)]
        retrieval_only = mode == BenchmarkMode.RETRIEVAL
        names = ["full"] if retrieval_only or not ablations else ablations
        configs = experiments(
            mode,
            names,
            k=k,
            max_attempts=max_attempts,
            timeout_seconds=timeout or settings.execution_timeout,
        )
        llm = None
        if mode != BenchmarkMode.RETRIEVAL:
            llm = require_provider(
                provider or llm_provider_from_settings(settings), "benchmarks"
            )
        sandbox = self._runner
        if sandbox is None and mode == BenchmarkMode.REPAIR:
            sandbox = DockerSandboxRunner(
                settings.sandbox_image, workspace_dir=settings.sandbox_workspace_dir
            )
        manifest = build_manifest(
            loaded, selected, configs, settings, llm.name if llm else None
        )
        runner = BenchmarkRunner(
            self._client,
            TaskExecutor(self._client, settings, sandbox, llm),
            RepositoryMaterializer(
                settings.data_dir / "benchmarks" / "repos", path.parent
            ),
            self._store,
        )
        manifest, summary = runner.run(loaded, manifest, progress)
        return BenchmarkRun(manifest=manifest, summary=summary)

    def load(self, run_id: str) -> BenchmarkRun:
        manifest, results = self._store.load(run_id)
        summary = summarize(run_id, manifest.suite, results)
        return BenchmarkRun(manifest=manifest, summary=summary, results=results)

    def runs(self) -> list[str]:
        return self._store.runs()
