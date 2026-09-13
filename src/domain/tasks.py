"""Typed task requests, lifecycle records, and public events."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from repoagent.domain.repository import RepositorySpec


class TaskKind(StrEnum):
    INDEX = "index"
    ANALYZE = "analyze"
    ASK = "ask"
    FIX = "fix"
    TEST = "test"
    BENCHMARK = "benchmark"


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    BLOCKED = "blocked"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class DomainModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class TaskRequest(DomainModel):
    kind: TaskKind
    repository: RepositorySpec | None = None
    description: str | None = None
    suite: str | None = None

    @model_validator(mode="after")
    def validate_request(self) -> "TaskRequest":
        if self.kind == TaskKind.BENCHMARK:
            if self.suite not in {
                "synthetic",
                "bugsinpy",
                "swe-bench",
                "swe-bench-verified",
            }:
                raise ValueError("Unknown benchmark suite")
            if self.repository is not None or self.description is not None:
                raise ValueError("Benchmark requests only accept a suite")
        else:
            if self.repository is None or self.suite is not None:
                raise ValueError("Repository requests require a source and no suite")
            if self.kind in {TaskKind.ASK, TaskKind.FIX}:
                if not self.description or not self.description.strip():
                    raise ValueError("A nonempty question or issue is required")
            elif self.description is not None:
                raise ValueError("This operation does not accept a description")
        return self


class TaskRecord(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    request: TaskRequest
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    message: str | None = None


class TaskEvent(DomainModel):
    task_id: UUID
    sequence: int = Field(ge=1)
    name: str
    status: TaskStatus
    timestamp: datetime
    message: str
