"""Background job records for long-running API operations (M8)."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import Field

from repoagent.analysis.models import AnalysisModel


def now() -> datetime:
    return datetime.now(UTC)


class JobKind(StrEnum):
    INVESTIGATE = "investigate"
    REPAIR = "repair"
    VALIDATED_REPAIR = "validated_repair"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

    @property
    def terminal(self) -> bool:
        return self in (JobStatus.SUCCEEDED, JobStatus.FAILED)


class JobEvent(AnalysisModel):
    at: datetime = Field(default_factory=now)
    status: JobStatus
    message: str = Field(default="", max_length=500)


class JobRecord(AnalysisModel):
    """Observable lifecycle only; results are stored separately as JSON."""

    id: str = Field(default_factory=lambda: uuid4().hex, pattern=r"^[0-9a-f]{32}$")
    kind: JobKind
    repository: str
    status: JobStatus = JobStatus.QUEUED
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
    events: list[JobEvent] = Field(default_factory=list)
    error: str | None = Field(default=None, max_length=1000)

    def transition(self, status: JobStatus, message: str = "") -> "JobRecord":
        return self.model_copy(
            update={
                "status": status,
                "updated_at": now(),
                "events": [*self.events, JobEvent(status=status, message=message)],
                "error": message if status == JobStatus.FAILED else self.error,
            }
        )
