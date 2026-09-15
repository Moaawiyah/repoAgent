"""Small public SDK mixin exposing the M8 benchmark capability."""

from typing import Protocol

from repoagent.config import Settings
from repoagent.ports.sandbox import SandboxRunner
from repoagent.sdk.benchmark import BenchmarkApi


class BenchmarkClient(Protocol):
    _settings: Settings | None
    _sandbox_runner: SandboxRunner | None


class BenchmarkCapability:
    def benchmarks(self: BenchmarkClient) -> BenchmarkApi:
        """Run benchmark suites and read stored runs (M8)."""
        return BenchmarkApi(self._settings or Settings(), self, self._sandbox_runner)
