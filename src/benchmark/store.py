"""JSONL benchmark result store: manifest.json, results.jsonl, summary.json."""

import re
from pathlib import Path

from pydantic import TypeAdapter

from repoagent.benchmark.provenance import RunManifest
from repoagent.benchmark.results import TaskResult
from repoagent.domain.errors import StorageError

_RUN = re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{6}$")


class JsonlResultStore:
    """Append-only per-run results; one directory per run, never overwritten."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def _dir(self, run_id: str) -> Path:
        if not _RUN.fullmatch(run_id):
            raise StorageError("Invalid benchmark run identifier")
        return self._root / run_id

    def start(self, manifest: RunManifest) -> Path:
        directory = self._dir(manifest.run_id)
        try:
            directory.mkdir(parents=True, exist_ok=False)
            (directory / "manifest.json").write_text(manifest.model_dump_json(indent=2))
        except OSError:
            raise StorageError("Could not create benchmark run directory") from None
        return directory

    def append(self, result: TaskResult) -> None:
        try:
            with (self._dir(result.run_id) / "results.jsonl").open("a") as stream:
                stream.write(result.model_dump_json() + "\n")
        except OSError:
            raise StorageError("Could not append benchmark result") from None

    def finish(self, manifest: RunManifest, summary_json: str) -> None:
        directory = self._dir(manifest.run_id)
        (directory / "manifest.json").write_text(manifest.model_dump_json(indent=2))
        (directory / "summary.json").write_text(summary_json)

    def load(self, run_id: str) -> tuple[RunManifest, list[TaskResult]]:
        directory = self._dir(run_id)
        try:
            manifest = RunManifest.model_validate_json(
                (directory / "manifest.json").read_text()
            )
            path = directory / "results.jsonl"
            lines = path.read_text().splitlines() if path.exists() else []
        except (OSError, ValueError):
            raise StorageError("Benchmark run is missing or invalid") from None
        adapter = TypeAdapter(TaskResult)
        return manifest, [adapter.validate_json(line) for line in lines if line]

    def runs(self) -> list[str]:
        if not self._root.is_dir():
            return []
        return sorted(p.name for p in self._root.iterdir() if _RUN.fullmatch(p.name))
