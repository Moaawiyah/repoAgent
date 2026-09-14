"""``SandboxRunner`` implementation backed by the Docker CLI.

Dependency preparation (optional network, no repository mounted) is separate
from validation (``--network none``, dependencies mounted read-only).
"""

import logging
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from repoagent.domain.errors import SandboxError
from repoagent.domain.sandbox import (
    DependencyStrategy,
    NetworkPolicy,
    SandboxLimits,
    ValidationPlan,
)
from repoagent.sandbox.docker_args import DockerCommandBuilder, validate_image
from repoagent.sandbox.docker_session import DockerSession
from repoagent.sandbox.process import ProcessRunner, SubprocessRunner
from repoagent.sandbox.workspace import WorkspaceLimits, WorkspaceManager
from repoagent.validation.policy import CommandPolicy

PROBE_TIMEOUT = 20
LOGGER = logging.getLogger(__name__)


class DockerSandboxRunner:
    """Creates one dependency cache per repair and a fresh copy per run."""

    def __init__(
        self,
        image: str,
        *,
        process: ProcessRunner | None = None,
        workspace_dir: Path | None = None,
    ) -> None:
        self._image = validate_image(image)
        self._process = process or SubprocessRunner()
        self._workspaces = WorkspaceManager(workspace_dir, WorkspaceLimits())
        self._workspace_dir = workspace_dir

    @contextmanager
    def session(
        self, repository: Path, plan: ValidationPlan, limits: SandboxLimits
    ) -> Iterator[DockerSession]:
        builder = DockerCommandBuilder(self._image, limits)
        policy = CommandPolicy(limits.allowed_commands)
        for spec in plan.commands:
            policy.argv(spec)
        try:
            probe = self._process.run(builder.probe(), PROBE_TIMEOUT, 4096)
        except OSError:
            raise SandboxError(
                "Docker CLI is not installed or not executable"
            ) from None
        if probe.timed_out or probe.exit_code != 0:
            raise SandboxError("Docker daemon is unavailable for sandbox execution")
        if self._workspace_dir is not None:
            self._workspace_dir.mkdir(parents=True, exist_ok=True)
        deps = Path(tempfile.mkdtemp(prefix="repoagent-deps-", dir=self._workspace_dir))
        LOGGER.info("Sandbox session opened", extra={"event": "sandbox_opened"})
        try:
            self._install(plan, deps, limits, builder, policy)
            yield DockerSession(
                repository,
                deps,
                limits,
                builder,
                self._process,
                self._workspaces,
                policy,
            )
        finally:
            shutil.rmtree(deps, ignore_errors=True)
            LOGGER.info("Sandbox session closed", extra={"event": "sandbox_closed"})

    def _install(
        self,
        plan: ValidationPlan,
        deps: Path,
        limits: SandboxLimits,
        builder: DockerCommandBuilder,
        policy: CommandPolicy,
    ) -> None:
        if limits.dependencies == DependencyStrategy.NONE or not plan.requirements:
            return
        name = f"repoagent-{uuid4().hex[:16]}"
        argv = policy.install_argv(plan.requirements)
        network = limits.network == NetworkPolicy.INSTALL_ONLY
        command = builder.run(name, argv, deps, None, network)
        result = self._process.run(
            command, limits.install_timeout_seconds, limits.max_output_bytes
        )
        if result.timed_out:
            self._process.run(builder.kill(name), PROBE_TIMEOUT, 4096)
        if result.timed_out or result.exit_code != 0:
            tail = result.stderr.strip().splitlines()[-1:] or ["no output"]
            raise SandboxError(f"Dependency preparation failed: {tail[0][:200]}")
