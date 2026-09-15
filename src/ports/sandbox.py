"""Sandbox boundary: application code never depends on Docker specifics."""

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Protocol

from repoagent.domain.sandbox import (
    CommandSpec,
    SandboxExecution,
    SandboxLimits,
    ValidationPlan,
)


class SandboxSession(Protocol):
    """Prepared dependencies for one repair; each run gets a fresh workspace."""

    def run(
        self,
        commands: list[CommandSpec],
        unified_diff: str | None,
        overlay: dict[str, str] | None = None,
    ) -> SandboxExecution:
        """Copy the repository, apply the diff, write evaluator overlay files, run.

        ``overlay`` is reserved for benchmark evaluators (hidden tests); agents
        never supply it.
        """
        ...


class SandboxRunner(Protocol):
    """Creates isolated sessions; implementations must clean up on exit."""

    def session(
        self, repository: Path, plan: ValidationPlan, limits: SandboxLimits
    ) -> AbstractContextManager[SandboxSession]:
        """Prepare dependencies; raise ``SandboxError`` when unavailable."""
        ...
