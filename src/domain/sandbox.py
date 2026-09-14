"""Typed, framework-free sandbox execution contracts (M7).

Commands are expressed as allowlisted kinds, never as shell strings; the
trusted argv for each kind lives in ``repoagent.validation.policy``.
"""

from enum import StrEnum

from pydantic import Field

from repoagent.analysis.models import AnalysisModel


class CommandKind(StrEnum):
    """Every operation RepoAgent may ever run inside a sandbox."""

    INSTALL = "install"
    PYTEST = "pytest"
    RUFF_CHECK = "ruff_check"


class NetworkPolicy(StrEnum):
    NONE = "none"
    INSTALL_ONLY = "install_only"


class CleanupPolicy(StrEnum):
    ALWAYS = "always"
    KEEP_FAILED_WORKSPACE = "keep_failed_workspace"


class DependencyStrategy(StrEnum):
    NONE = "none"
    TOOLS = "tools"
    PROJECT = "project"


class SandboxLimits(AnalysisModel):
    """Resource and policy bounds applied to every sandbox command."""

    timeout_seconds: int = Field(default=300, ge=1, le=3600)
    install_timeout_seconds: int = Field(default=600, ge=1, le=3600)
    memory_mb: int = Field(default=1024, ge=64, le=65536)
    cpus: float = Field(default=2.0, gt=0, le=64)
    pids_limit: int = Field(default=256, ge=16, le=4096)
    max_output_bytes: int = Field(default=64000, ge=1024, le=10_000_000)
    network: NetworkPolicy = NetworkPolicy.INSTALL_ONLY
    cleanup: CleanupPolicy = CleanupPolicy.ALWAYS
    allowed_commands: frozenset[CommandKind] = frozenset(
        {CommandKind.PYTEST, CommandKind.RUFF_CHECK}
    )
    dependencies: DependencyStrategy = DependencyStrategy.PROJECT


class CommandSpec(AnalysisModel):
    """One validation step; ``required`` steps gate a VALIDATED result."""

    kind: CommandKind
    required: bool = True


class ValidationPlan(AnalysisModel):
    """Statically detected commands and wheel-only dependency specs."""

    commands: list[CommandSpec] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    skipped_requirements: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    def has(self, kind: CommandKind) -> bool:
        return any(command.kind == kind for command in self.commands)


class CommandResult(AnalysisModel):
    """Captured outcome of one command with bounded output."""

    kind: CommandKind
    argv: list[str]
    exit_code: int | None = None
    duration_seconds: float = Field(default=0.0, ge=0)
    timed_out: bool = False
    stdout: str = ""
    stderr: str = ""
    output_truncated: bool = False


class SandboxOutcome(StrEnum):
    COMPLETED = "completed"
    PATCH_APPLY_FAILED = "patch_apply_failed"
    SANDBOX_ERROR = "sandbox_error"
    TIMEOUT = "timeout"


class SandboxExecution(AnalysisModel):
    """One disposable-workspace run: patch application plus commands."""

    outcome: SandboxOutcome
    commands: list[CommandResult] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list, max_length=20)
    duration_seconds: float = Field(default=0.0, ge=0)
    cleaned_up: bool = False
    repository_unchanged: bool = True

    def result(self, kind: CommandKind) -> CommandResult | None:
        return next((item for item in self.commands if item.kind == kind), None)
