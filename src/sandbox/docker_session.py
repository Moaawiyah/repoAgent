"""One repair's Docker session: every run uses a new disposable workspace."""

import time
from pathlib import Path
from uuid import uuid4

from repoagent.domain.errors import WorkspaceError
from repoagent.domain.sandbox import (
    CleanupPolicy,
    CommandResult,
    CommandSpec,
    SandboxExecution,
    SandboxLimits,
    SandboxOutcome,
)
from repoagent.sandbox.docker_args import DockerCommandBuilder
from repoagent.sandbox.patching import WorkspacePatcher
from repoagent.sandbox.process import ProcessRunner
from repoagent.sandbox.workspace import Workspace, WorkspaceManager, fingerprint
from repoagent.validation.policy import CommandPolicy

DOCKER_FAILURE_EXITS = {125, 126, 127}
KILL_TIMEOUT = 30


class DockerSession:
    def __init__(
        self,
        repository: Path,
        deps: Path,
        limits: SandboxLimits,
        builder: DockerCommandBuilder,
        process: ProcessRunner,
        workspaces: WorkspaceManager,
        policy: CommandPolicy,
    ) -> None:
        self._repository, self._deps, self._limits = repository, deps, limits
        self._builder, self._process = builder, process
        self._workspaces, self._policy = workspaces, policy

    def run(
        self, commands: list[CommandSpec], unified_diff: str | None
    ) -> SandboxExecution:
        argvs = [self._policy.argv(spec) for spec in commands]
        start, before = time.monotonic(), fingerprint(self._repository)
        try:
            workspace = self._workspaces.create(self._repository)
        except WorkspaceError as error:
            return SandboxExecution(
                outcome=SandboxOutcome.SANDBOX_ERROR, errors=[str(error)[:500]]
            )
        outcome, results, errors = SandboxOutcome.COMPLETED, [], []
        try:
            if unified_diff is not None:
                WorkspacePatcher().apply(workspace.path, unified_diff)
            for spec, argv in zip(commands, argvs, strict=True):
                result = self._execute(spec, argv, workspace)
                results.append(result)
                if result.timed_out:
                    outcome = SandboxOutcome.TIMEOUT
                    break
                if result.exit_code in DOCKER_FAILURE_EXITS:
                    outcome = SandboxOutcome.SANDBOX_ERROR
                    errors.append(f"Container could not run {spec.kind.value}")
                    break
        except WorkspaceError as error:
            outcome = SandboxOutcome.PATCH_APPLY_FAILED
            errors.append(str(error)[:500])
        except OSError:
            outcome = SandboxOutcome.SANDBOX_ERROR
            errors.append("Docker CLI invocation failed")
        finally:
            cleaned = self._cleanup(workspace, outcome, results)
        return SandboxExecution(
            outcome=outcome,
            commands=results,
            errors=errors,
            duration_seconds=time.monotonic() - start,
            cleaned_up=cleaned,
            repository_unchanged=fingerprint(self._repository) == before,
        )

    def _execute(
        self, spec: CommandSpec, argv: list[str], workspace: Workspace
    ) -> CommandResult:
        name = f"repoagent-{uuid4().hex[:16]}"
        command = self._builder.run(name, argv, self._deps, workspace.path, False)
        limits = self._limits
        result = self._process.run(
            command, limits.timeout_seconds, limits.max_output_bytes
        )
        if result.timed_out:
            self._process.run(self._builder.kill(name), KILL_TIMEOUT, 4096)
        return CommandResult(
            kind=spec.kind,
            argv=argv,
            exit_code=result.exit_code,
            duration_seconds=round(result.duration_seconds, 3),
            timed_out=result.timed_out,
            stdout=result.stdout,
            stderr=result.stderr,
            output_truncated=result.truncated,
        )

    def _cleanup(
        self,
        workspace: Workspace,
        outcome: SandboxOutcome,
        results: list[CommandResult],
    ) -> bool:
        failed = outcome != SandboxOutcome.COMPLETED or any(
            item.exit_code != 0 for item in results
        )
        if self._limits.cleanup == CleanupPolicy.KEEP_FAILED_WORKSPACE and failed:
            return False
        return self._workspaces.destroy(workspace)
