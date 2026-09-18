"""In-process worker pool: HTTP requests enqueue work and return immediately.

A durable broker (Redis/RQ, Celery, SQS) can implement the same ``JobQueue``
port for multi-process deployments; this adapter is for local/demo use.
"""

import logging
from concurrent.futures import ThreadPoolExecutor

from repoagent.domain.errors import RepoAgentError
from repoagent.domain.jobs import JobKind, JobRecord, JobStatus
from repoagent.domain.workflow import StageStatus, WorkflowStage
from repoagent.ports.jobs import JobStore, Work

LOGGER = logging.getLogger(__name__)


class _JobRun:
    """Tracks one job's record so progress events persist as they happen."""

    def __init__(self, store: JobStore, record: JobRecord) -> None:
        self.store, self.record = store, record

    def move(self, status: JobStatus, message: str) -> None:
        self.record = self.record.transition(status, message)
        self.store.save(self.record)

    def __call__(self, message: str) -> None:
        self.move(JobStatus.RUNNING, message[:500])

    def stage(self, key: str, status: StageStatus, detail: str = "") -> None:
        self.record = self.record.stage(key, status, detail)
        self.store.save(self.record)


class LocalJobQueue:
    def __init__(self, store: JobStore, max_workers: int = 1) -> None:
        self._store = store
        self._pool = ThreadPoolExecutor(max_workers=max_workers)

    def submit(
        self,
        kind: JobKind,
        repository: str,
        work: Work,
        stages: list[WorkflowStage] | None = None,
    ) -> JobRecord:
        record = JobRecord(
            kind=kind, repository=repository, stages=stages or []
        ).transition(JobStatus.QUEUED, "Job accepted")
        self._store.save(record)
        self._pool.submit(self._run, _JobRun(self._store, record), work)
        return record

    def _run(self, run: _JobRun, work: Work) -> None:
        run.move(JobStatus.RUNNING, "Worker started")
        try:
            result = work(run)
        except RepoAgentError as error:
            run.move(JobStatus.FAILED, str(error)[:500])
        except Exception:  # noqa: BLE001 - boundary: never crash the worker thread
            LOGGER.exception(
                "Job failed", extra={"event": "job_failed", "task_id": run.record.id}
            )
            run.move(JobStatus.FAILED, "Internal error")
        else:
            self._store.save_result(run.record.id, result)
            run.move(JobStatus.SUCCEEDED, type(result).__name__)

    def shutdown(self, wait: bool = True) -> None:
        self._pool.shutdown(wait=wait)
