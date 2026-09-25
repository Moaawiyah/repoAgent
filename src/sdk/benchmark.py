"""Public SDK capability for M8 benchmark runs and stored results."""

from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from repoagent.ai.openai_provider import llm_provider_from_settings
from repoagent.ai.provider import LLMProvider, require_provider
from repoagent.benchmark.environment import image_digest
from repoagent.benchmark.experiment import BenchmarkMode, experiments
from repoagent.benchmark.loaders import load_suite, resolve_suite
from repoagent.benchmark.materialize import RepositoryMaterializer
from repoagent.benchmark.metrics import BenchmarkSummary, summarize
from repoagent.benchmark.models import BenchmarkSuite
from repoagent.benchmark.provenance import RunManifest, build_manifest
from repoagent.benchmark.rebench import import_swerebench
from repoagent.benchmark.results import TaskResult
from repoagent.benchmark.runner import BenchmarkRunner
from repoagent.benchmark.store import JsonlResultStore
from repoagent.benchmark.task_executor import TaskExecutor
from repoagent.benchmark.verify import TaskCheck, verify_task
from repoagent.config import Settings
from repoagent.domain.errors import RepoAgentError
from repoagent.ports.sandbox import SandboxRunner


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
        names = ablations or ["full"]
        configs = experiments(
            mode,
            names,
            k=k,
            max_attempts=max_attempts,
            timeout_seconds=timeout or settings.execution_timeout,
        )
        llm = None
        if mode != BenchmarkMode.RETRIEVAL or any(c.reranker == "llm" for c in configs):
            llm = require_provider(
                provider or llm_provider_from_settings(settings), "benchmarks"
            )
        # Repair mode builds one Docker runner per task image unless injected.
        sandbox = self._runner
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

    def verify(
        self, suite: str | Path, *, task_ids: list[str] | None = None
    ) -> list[TaskCheck]:
        """Check each task's pinned environment, hidden tests, and gold patch."""
        path = resolve_suite(str(suite))
        loaded = load_suite(path)
        materializer = RepositoryMaterializer(
            self._settings.data_dir / "benchmarks" / "repos", path.parent
        )
        checks = []
        for task in loaded.select(task_ids):
            try:
                checkout = materializer.materialize(task.repository)
            except RepoAgentError as error:
                checks.append(TaskCheck(task_id=task.task_id, reason=str(error)))
                continue
            checks.append(verify_task(task, checkout, self._settings, self._runner))
        return checks

    def import_swerebench(
        self, records: list[dict], instance_ids: list[str], image: str
    ) -> tuple[BenchmarkSuite, dict[str, str]]:
        """Import rows with hidden tests and a digest-pinned image per task.

        ``image`` is a template such as ``python:{python}-slim``; each
        resolves to ``repo@sha256:...`` when the image is present locally.
        """
        materializer = RepositoryMaterializer(
            self._settings.data_dir / "benchmarks" / "repos", Path.cwd()
        )

        def image_for(python: str) -> str:
            tag = image.format(python=python)
            return image_digest(tag) or tag

        return import_swerebench(records, instance_ids, materializer, image_for)
