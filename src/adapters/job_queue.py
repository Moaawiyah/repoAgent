"""In-process worker pool: HTTP requests enqueue work and return immediately.

A durable broker (Redis/RQ, Celery, SQS) can implement the same ``JobQueue``
port for multi-process deployments; this adapter is for local/demo use.

Deterministic task-timeout watchdog: a ``threading.Timer`` marks a job
``FAILED`` once ``task_timeout_seconds`` elapses, independent of whether the
work is currently making LLM calls (unlike ``BudgetedProvider``'s deadline,
which is only checked at LLM call boundaries). This is not an LLM agent and
makes no judgment calls; it only reports a deterministic deadline. Python has
no safe way to forcibly kill a running thread, so the watchdog cannot stop
in-flight work that ignores its own bounds (e.g. a stuck subprocess without
its own timeout) — it only guarantees the job is *reported* terminal by the
deadline, guarded so a late natural completion can never overwrite it.
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor

from repoagent.domain.errors import RepoAgentError
from repoagent.domain.jobs import JobKind, JobRecord, JobStatus
from repoagent.domain.workflow import StageStatus, WorkflowStage
from repoagent.ports.jobs import JobStore, Work

LOGGER = logging.getLogger(__name__)
TIMEOUT_MESSAGE = "Task time limit reached"


class _JobRun:
    """Tracks one job's record; guards against writes after a terminal status."""

    def __init__(self, store: JobStore, record: JobRecord) -> None:
        self.store, self.record = store, record
        self._lock = threading.Lock()

    def move(self, status: JobStatus, message: str) -> None:
        with self._lock:
            if self.record.status.terminal:
                return
            self.record = self.record.transition(status, message)
            self.store.save(self.record)

    def __call__(self, message: str) -> None:
        self.move(JobStatus.RUNNING, message[:500])

    def stage(self, key: str, status: StageStatus, detail: str = "") -> None:
        with self._lock:
            if self.record.status.terminal:
                return
            self.record = self.record.stage(key, status, detail)
            self.store.save(self.record)


class LocalJobQueue:
    def __init__(
        self,
        store: JobStore,
        max_workers: int = 1,
        task_timeout_seconds: float | None = None,
    ) -> None:
        self._store = store
        self._pool = ThreadPoolExecutor(max_workers=max_workers)
        self._task_timeout = task_timeout_seconds

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
        watchdog = self._watchdog(run)
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
        finally:
            if watchdog is not None:
                watchdog.cancel()

    def _watchdog(self, run: _JobRun) -> threading.Timer | None:
        if self._task_timeout is None:
            return None
        timer = threading.Timer(
            self._task_timeout, run.move, args=(JobStatus.FAILED, TIMEOUT_MESSAGE)
        )
        timer.daemon = True
        timer.start()
        return timer

    def shutdown(self, wait: bool = True) -> None:
        self._pool.shutdown(wait=wait)
