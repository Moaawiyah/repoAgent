"""Load RepoAgent-format suites; external datasets are imported by adapters."""

import json
from pathlib import Path

from repoagent.benchmark.models import BenchmarkSuite
from repoagent.domain.errors import RepoAgentError

MAX_SUITE_BYTES = 50_000_000
SUITE_DIRECTORY = Path("benchmarks")


class BenchmarkError(RepoAgentError):
    """A benchmark suite or run could not be loaded or executed."""


def resolve_suite(name_or_path: str) -> Path:
    """Accept a suite file path or a name under ``./benchmarks/<name>.json``."""
    candidate = Path(name_or_path)
    if candidate.suffix == ".json" and candidate.is_file():
        return candidate.resolve()
    named = SUITE_DIRECTORY / f"{name_or_path}.json"
    if "/" not in name_or_path and named.is_file():
        return named.resolve()
    raise BenchmarkError(f"Benchmark suite not found: {name_or_path}")


def load_suite(path: Path) -> BenchmarkSuite:
    try:
        if path.stat().st_size > MAX_SUITE_BYTES:
            raise BenchmarkError("Benchmark suite file is too large")
        return BenchmarkSuite.model_validate_json(path.read_text(encoding="utf-8"))
    except OSError:
        raise BenchmarkError(f"Cannot read benchmark suite: {path}") from None


def read_records(path: Path) -> list[dict]:
    """Read a JSON array or JSON Lines dataset export."""
    text = path.read_text(encoding="utf-8")
    if text.lstrip().startswith("["):
        return list(json.loads(text))
    return [json.loads(line) for line in text.splitlines() if line.strip()]
