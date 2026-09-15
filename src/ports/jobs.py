"""Job queue and store boundaries; replaceable by a durable queue later."""

from collections.abc import Callable
from typing import Protocol

from pydantic import BaseModel

from repoagent.domain.jobs import JobKind, JobRecord

Progress = Callable[[str], None]
Work = Callable[[Progress], BaseModel]


class JobStore(Protocol):
    def save(self, record: JobRecord) -> None: ...

    def get(self, job_id: str) -> JobRecord: ...

    def recent(self, limit: int) -> list[JobRecord]: ...

    def save_result(self, job_id: str, result: BaseModel) -> None: ...

    def result(self, job_id: str) -> str: ...


class JobQueue(Protocol):
    def submit(self, kind: JobKind, repository: str, work: Work) -> JobRecord: ...
