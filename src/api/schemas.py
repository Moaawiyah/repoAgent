"""Validated API request bodies; responses reuse typed SDK models."""

from pydantic import BaseModel, ConfigDict, Field

from repoagent.domain.investigation import Issue
from repoagent.retrieval.models import RetrievalStrategy


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RepositoryBody(Body):
    repository: str = Field(min_length=1, max_length=1000)


class SearchBody(RepositoryBody):
    query: str = Field(min_length=1, max_length=1000)
    strategy: RetrievalStrategy = RetrievalStrategy.HYBRID_GRAPH
    top_k: int = Field(default=5, ge=1, le=20)


class InvestigateBody(RepositoryBody):
    issue: Issue | str
    max_iterations: int | None = Field(default=None, ge=1, le=10)
    top_k: int = Field(default=5, ge=1, le=10)


class RepairBody(InvestigateBody):
    execute: bool = False
    max_attempts: int | None = Field(default=None, ge=1, le=10)
    max_revisions: int | None = Field(default=None, ge=0, le=5)
    timeout: int | None = Field(default=None, ge=1, le=3600)


class RepairTaskBody(Body):
    repository_url: str = Field(min_length=1, max_length=300)
    issue: str = Field(min_length=10, max_length=6000)
    sandbox_validation: bool = False


class DiscoverTaskBody(Body):
    repository_url: str = Field(min_length=1, max_length=300)
    limit: int | None = Field(default=None, ge=1, le=50)


class FindingRepairBody(Body):
    sandbox_validation: bool = False
