"""Small public SDK mixin exposing the web workflows."""

from typing import Protocol

from repoagent.config import Settings
from repoagent.ports.sandbox import SandboxRunner
from repoagent.sdk.retrieval import RetrievalApi
from repoagent.sdk.workflows import Loader, WorkflowApi


class WorkflowClient(Protocol):
    _settings: Settings | None
    _sandbox_runner: SandboxRunner | None

    def retrieval(self) -> RetrievalApi: ...


class WorkflowCapability:
    def workflows(self: WorkflowClient, *, loader: Loader | None = None) -> WorkflowApi:
        """RepairGraph / DiscoveryGraph over local paths or GitHub URLs."""
        return WorkflowApi(self, self._settings or Settings(), loader)
