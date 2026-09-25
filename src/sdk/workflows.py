"""Public SDK capability for the RepairGraph and DiscoveryGraph workflows.

Composes existing SDK operations (index, repair, repair_and_validate) and
audit components; it adds repository loading, deterministic budgets and
progress, not a second repair or retrieval pipeline.
"""

from collections.abc import Callable
from pathlib import Path

from repoagent.adapters.github_source import GitHubRepositorySource
from repoagent.ai.budget import BudgetedProvider
from repoagent.ai.openai_provider import llm_provider_from_settings
from repoagent.ai.provider import LLMProvider
from repoagent.config import Settings
from repoagent.domain.errors import RepositoryInvalid
from repoagent.domain.github import RepositoryHandle, parse_github_url
from repoagent.domain.investigation import Issue
from repoagent.domain.limits import WorkflowLimits
from repoagent.domain.workflow_results import (
    DiscoveryWorkflowResult,
    RepairWorkflowResult,
    WorkflowUsage,
)
from repoagent.workflows.discovery_graph import DiscoveryGraph
from repoagent.workflows.discovery_nodes import DiscoveryDeps
from repoagent.workflows.guards import required
from repoagent.workflows.progress import StageSink, ignore_stage
from repoagent.workflows.repair_graph import RepairGraph, RepairPorts

Loader = Callable[[str], RepositoryHandle]


def is_remote(source: str) -> bool:
    return "://" in source or source.startswith(("github.com/", "git@"))


class WorkflowApi:
    def __init__(self, client, settings: Settings, loader: Loader | None) -> None:
        self._client, self._settings, self._loader = client, settings, loader
        self.limits = WorkflowLimits.from_settings(settings)

    def open_repository(self, source: str) -> RepositoryHandle:
        """GitHub URLs are fetched into an isolated workspace; paths are used as-is."""
        if self._loader is not None:
            return self._loader(source)
        if is_remote(source):
            settings = self._settings
            fetcher = GitHubRepositorySource(
                settings.data_dir / "workspaces",
                timeout=settings.github_clone_timeout,
                max_bytes=settings.github_max_repository_mb * 1024 * 1024,
            )
            return fetcher.materialize(parse_github_url(source))
        path = Path(source).expanduser().resolve()
        if not path.is_dir():
            raise RepositoryInvalid("Repository path is not a directory")
        return RepositoryHandle(source=str(path), name=path.name, path=str(path))

    def _budget(self, provider: LLMProvider | None) -> BudgetedProvider | None:
        llm = provider or llm_provider_from_settings(self._settings)
        if llm is None:
            return None
        return BudgetedProvider(
            llm,
            max_calls=self.limits.llm_calls,
            max_tokens=self.limits.tokens,
            timeout_seconds=self.limits.task_timeout_seconds,
        )

    @staticmethod
    def _usage(budget: BudgetedProvider | None) -> WorkflowUsage:
        if budget is None:
            return WorkflowUsage()
        return WorkflowUsage(llm_calls=budget.calls, tokens=budget.tokens)

    def repair(
        self,
        source: str,
        issue: Issue | str,
        *,
        execute: bool = False,
        provider: LLMProvider | None = None,
        progress: StageSink = ignore_stage,
        handle: RepositoryHandle | None = None,
        source_finding: str | None = None,
    ) -> RepairWorkflowResult:
        """Run RepairGraph; ``execute`` adds Docker validation (M7 sandbox)."""
        issue = Issue(description=issue) if isinstance(issue, str) else issue
        client, llm = self._client, self._budget(provider)

        def repair(path: Path, target: Issue, sandboxed: bool):
            if sandboxed:
                return client.repair_and_validate(path, target, provider=llm)
            return client.repair(path, target, provider=llm)

        ports = RepairPorts(
            load=(lambda _: handle) if handle else self.open_repository,
            index=client.index,
            repair=repair,
        )
        state = RepairGraph(ports, progress).run(source, issue, execute)
        return RepairWorkflowResult(
            repository=state.handle,
            issue=issue,
            sandbox_validation=execute,
            index=state.index,
            report=state.report,
            source_finding=source_finding,
            limits=self.limits,
            usage=self._usage(llm),
        )

    def discover(
        self,
        source: str,
        *,
        limit: int | None = None,
        provider: LLMProvider | None = None,
        progress: StageSink = ignore_stage,
    ) -> DiscoveryWorkflowResult:
        """Run DiscoveryGraph; never repairs anything by itself."""
        store, embedding = self._client.retrieval()._services()
        llm = self._budget(provider)
        deps = DiscoveryDeps(
            store, embedding, llm, self._client._sandbox_runner, self.open_repository
        )
        bounded = limit if limit is not None else self.limits.discovery_candidates
        state = DiscoveryGraph(deps, progress).run(source, bounded)
        handle = required(state.handle, "handle")
        return DiscoveryWorkflowResult(
            repository=handle,
            report=DiscoveryGraph.report(state, handle.source),
            limits=self.limits,
            usage=self._usage(llm),
        )
