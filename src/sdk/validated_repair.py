"""Public SDK capability for M7 sandboxed, validated repairs."""

from pathlib import Path

from repoagent.adapters.json_report import write_report
from repoagent.agent.execution_state import RepairLoopLimits
from repoagent.ai.openai_provider import llm_provider_from_settings
from repoagent.ai.provider import LLMProvider
from repoagent.application.validated_repair import (
    ValidatedRepairRequest,
    ValidatedRepairService,
)
from repoagent.config import Settings
from repoagent.domain.features import RepairFeatures
from repoagent.domain.investigation import InvestigationLimits, Issue
from repoagent.domain.repair_execution import ValidatedRepairReport
from repoagent.domain.sandbox import CommandKind, SandboxLimits
from repoagent.ports.sandbox import SandboxRunner
from repoagent.retrieval.configured import graph_policy_from_settings
from repoagent.sandbox.docker_runner import DockerSandboxRunner
from repoagent.sdk.retrieval import RetrievalApi


def pinned_requirements(settings: Settings) -> tuple[str, ...]:
    """Explicit pins from settings plus an optional requirements file."""
    pins = list(settings.sandbox_pinned_requirements)
    if settings.sandbox_requirements_file is not None:
        text = settings.sandbox_requirements_file.read_text(encoding="utf-8")
        pins += [
            line.strip()
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    return tuple(dict.fromkeys(pins))


def sandbox_limits(settings: Settings, timeout: int | None) -> SandboxLimits:
    return SandboxLimits(
        timeout_seconds=timeout if timeout is not None else settings.execution_timeout,
        install_timeout_seconds=settings.sandbox_install_timeout,
        memory_mb=settings.sandbox_memory_mb,
        cpus=settings.sandbox_cpus,
        pids_limit=settings.sandbox_pids_limit,
        max_output_bytes=settings.sandbox_max_output_bytes,
        network=settings.sandbox_network,
        cleanup=settings.sandbox_cleanup,
        allowed_commands=frozenset(
            CommandKind(item) for item in settings.sandbox_allowed_commands
        ),
        dependencies=settings.sandbox_dependencies,
        pinned_requirements=pinned_requirements(settings),
    )


class ValidatedRepairApi:
    def __init__(
        self,
        settings: Settings,
        retrieval: RetrievalApi,
        runner: SandboxRunner | None = None,
    ) -> None:
        self._settings, self._retrieval, self._runner = settings, retrieval, runner

    def repair(
        self,
        source: str | Path,
        issue: Issue | str,
        *,
        max_attempts: int | None = None,
        max_revisions: int | None = None,
        timeout: int | None = None,
        provider: LLMProvider | None = None,
        features: RepairFeatures | None = None,
    ) -> ValidatedRepairReport:
        settings = self._settings
        request = ValidatedRepairRequest(
            repository=str(source),
            issue=issue,
            loop=RepairLoopLimits(
                max_attempts=max_attempts
                if max_attempts is not None
                else settings.repair_max_attempts,
                max_revisions=max_revisions
                if max_revisions is not None
                else settings.repair_max_revisions,
                max_reinvestigations=settings.repair_max_reinvestigations,
            ),
            sandbox=sandbox_limits(settings, timeout),
            features=features or RepairFeatures(),
        )
        runner = self._runner or DockerSandboxRunner(
            settings.sandbox_image, workspace_dir=settings.sandbox_workspace_dir
        )
        store, embedding = self._retrieval._services()
        limits = InvestigationLimits(
            max_iterations=settings.investigation_max_iterations,
            max_queries=settings.investigation_max_queries,
            max_evidence=settings.investigation_max_evidence,
            max_tool_calls=settings.investigation_max_tool_calls,
            context_chars=settings.investigation_context_chars,
        )
        llm = provider or llm_provider_from_settings(settings)
        policy = graph_policy_from_settings(settings)
        service = ValidatedRepairService(store, embedding, llm, runner, limits, policy)
        report = service.repair(request)
        write_report(
            settings.data_dir / "repairs",
            report.task_id,
            report.repository,
            report.model_dump_json(indent=2),
        )
        return report
