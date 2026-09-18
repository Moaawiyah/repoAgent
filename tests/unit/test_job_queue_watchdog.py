"""Deterministic task-timeout watchdog: no LLM, guarded against late races."""

import threading
import time

from pydantic import BaseModel

from repoagent.adapters.job_queue import TIMEOUT_MESSAGE, LocalJobQueue, _JobRun
from repoagent.adapters.job_store import FileJobStore
from repoagent.domain.jobs import JobKind, JobStatus


class Done(BaseModel):
    ok: bool = True


def wait_terminal(store, job_id, limit=2.0):
    started = time.monotonic()
    while time.monotonic() - started < limit:
        record = store.get(job_id)
        if record.status.terminal:
            return record
        time.sleep(0.01)
    raise AssertionError("job did not reach a terminal status in time")


def test_stuck_job_is_marked_failed_once_the_task_deadline_passes(tmp_path):
    store = FileJobStore(tmp_path)
    queue = LocalJobQueue(store, task_timeout_seconds=0.05)
    release = threading.Event()

    def stuck(progress) -> Done:
        progress("working")
        release.wait(timeout=5)  # never returns before the watchdog fires
        return Done()

    record = queue.submit(JobKind.DISCOVER, "r", stuck, [])
    failed = wait_terminal(store, record.id)
    assert failed.status == JobStatus.FAILED
    assert failed.error == TIMEOUT_MESSAGE

    # The stuck worker eventually "completes"; its late success must not
    # overwrite the already-reported timeout.
    release.set()
    queue.shutdown(wait=True)
    final = store.get(record.id)
    assert final.status == JobStatus.FAILED and final.error == TIMEOUT_MESSAGE


def test_a_job_finishing_before_the_deadline_is_unaffected(tmp_path):
    store = FileJobStore(tmp_path)
    queue = LocalJobQueue(store, task_timeout_seconds=5)

    def fast(progress) -> Done:
        return Done()

    record = queue.submit(JobKind.DISCOVER, "r", fast, [])
    finished = wait_terminal(store, record.id)
    queue.shutdown(wait=True)
    assert finished.status == JobStatus.SUCCEEDED


def test_no_timeout_configured_means_no_watchdog_is_scheduled(tmp_path):
    store = FileJobStore(tmp_path)
    queue = LocalJobQueue(
        store
    )  # task_timeout_seconds=None: default, unchanged behavior
    record = queue.submit(JobKind.DISCOVER, "r", lambda progress: Done(), [])
    assert queue._watchdog(_JobRun(store, record)) is None
    queue.shutdown(wait=True)
