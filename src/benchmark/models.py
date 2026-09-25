"""Benchmark task and suite definitions; labels never reach agent context."""

import re
from enum import StrEnum

from pydantic import Field, field_validator

from repoagent.analysis.models import AnalysisModel

_GITHUB = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?(\.git)?$")
_SHA = re.compile(r"^[0-9a-f]{40}$")


class ExpectedOutcome(StrEnum):
    VALIDATED_REPAIR = "validated_repair"
    LOCALIZATION_ONLY = "localization_only"


class RepositoryRef(AnalysisModel):
    """A local directory (relative to the suite file) or a pinned GitHub commit."""

    source: str = Field(min_length=1, max_length=500)
    commit: str | None = None

    @property
    def is_remote(self) -> bool:
        return self.source.startswith("https://")

    @field_validator("commit")
    @classmethod
    def _commit(cls, value: str | None) -> str | None:
        if value is not None and not _SHA.fullmatch(value):
            raise ValueError("Commits must be full 40-character lowercase SHAs")
        return value

    def model_post_init(self, _context: object) -> None:
        if self.is_remote and (not _GITHUB.fullmatch(self.source) or not self.commit):
            raise ValueError("Remote repositories must be pinned GitHub commits")


class ValidationCriteria(AnalysisModel):
    """Evaluator-only checks: hidden tests are added after the agent finishes."""

    fail_to_pass: list[str] = Field(default_factory=list, max_length=200)
    pass_to_pass: list[str] = Field(default_factory=list, max_length=2000)
    hidden_tests: dict[str, str] = Field(default_factory=dict, max_length=20)


class TaskEnvironment(AnalysisModel):
    """Pinned execution environment making a repair task reproducible.

    ``image`` should be digest-pinned (``python:3.11-slim@sha256:...``);
    ``requirements`` are exact pins that replace the project's declared
    dependency ranges inside the sandbox.
    """

    image: str | None = Field(default=None, max_length=255)
    python: str | None = Field(default=None, pattern=r"^3\.\d{1,2}$")
    requirements: list[str] = Field(default_factory=list, max_length=500)


class BenchmarkTask(AnalysisModel):
    task_id: str = Field(pattern=r"^[A-Za-z0-9_.:@+-]{1,120}$")
    benchmark: str = Field(pattern=r"^[a-z0-9_-]{1,60}$")
    repository: RepositoryRef
    issue: str = Field(min_length=1, max_length=6000)
    issue_source: str = "issue"
    expected_files: list[str] = Field(default_factory=list)
    expected_symbols: list[str] = Field(default_factory=list)
    gold_patch: str | None = Field(default=None, max_length=200_000)
    validation: ValidationCriteria = ValidationCriteria()
    expected_outcome: ExpectedOutcome = ExpectedOutcome.LOCALIZATION_ONLY
    environment: TaskEnvironment | None = None


class BenchmarkSuite(AnalysisModel):
    name: str = Field(pattern=r"^[a-z0-9_-]{1,60}$")
    description: str = ""
    source: str = Field(default="", description="Dataset name and revision")
    tasks: list[BenchmarkTask] = Field(min_length=1)

    def select(self, task_ids: list[str] | None) -> list[BenchmarkTask]:
        if not task_ids:
            return list(self.tasks)
        known = {task.task_id: task for task in self.tasks}
        missing = [item for item in task_ids if item not in known]
        if missing:
            raise ValueError(f"Unknown benchmark task(s): {', '.join(missing)}")
        return [known[item] for item in task_ids]
