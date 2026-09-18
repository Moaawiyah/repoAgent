"""Composition root shared by API routes (constructed once per app)."""

from dataclasses import dataclass

from repoagent.ai.provider import LLMProvider
from repoagent.api.policy import ApiPolicy
from repoagent.ports.jobs import JobQueue, JobStore
from repoagent.sdk import RepoAgent
from repoagent.sdk.workflows import Loader


@dataclass(frozen=True)
class ApiContext:
    client: RepoAgent
    policy: ApiPolicy
    jobs: JobQueue
    store: JobStore
    provider: LLMProvider | None = None
    loader: Loader | None = None
