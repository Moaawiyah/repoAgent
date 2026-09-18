"""Stage bookkeeping on job records and the local queue's progress reporter."""

import time

from pydantic import BaseModel

from repoagent.adapters.job_queue import LocalJobQueue
from repoagent.adapters.job_store import FileJobStore
from repoagent.domain.errors import RepoAgentError
from repoagent.domain.jobs import JobKind, JobRecord, JobStatus
from repoagent.domain.workflow import (
    StageStatus,
    WorkflowKind,
    advance,
    initial_stages,
    settle,
)


class Done(BaseModel):
    ok: bool = True


def statuses(stages):
    return {stage.key: stage.status for stage in stages}


def test_initial_stages_are_distinct_per_workflow():
    repair = [s.key for s in initial_stages(WorkflowKind.REPAIR)]
    discover = [s.key for s in initial_stages(WorkflowKind.DISCOVER)]
    assert repair[:3] == ["repository", "analysis", "graph"]
    assert "docker_validation" in repair and "verifier" not in repair
    assert discover[-2:] == ["verifier", "report"]
    assert all(s.status == StageStatus.PENDING for s in initial_stages("repair"))


def test_entering_a_stage_completes_the_previous_and_counts_loops():
    stages = initial_stages(WorkflowKind.REPAIR)
    for key in ("developer", "reviewer", "developer"):
        stages = advance(stages, key, StageStatus.RUNNING)
    by_key = {s.key: s for s in stages}
    assert by_key["developer"].status == StageStatus.RUNNING
    assert by_key["developer"].visits == 2
    assert by_key["reviewer"].status == StageStatus.DONE
    stages = advance(stages, "reviewer", StageStatus.FAILED, "rejected")
    assert {s.key: s for s in stages}["reviewer"].detail == "rejected"
    assert advance(stages, "unknown", StageStatus.RUNNING) != stages  # closes dev
    closed = statuses(settle(stages, succeeded=False))
    assert closed["developer"] == StageStatus.FAILED
    assert closed["docker_validation"] == StageStatus.SKIPPED
    assert closed["reviewer"] == StageStatus.FAILED


def test_job_record_settles_stages_on_terminal_transition():
    record = JobRecord(
        kind=JobKind.DISCOVER, repository="r", stages=initial_stages("discover")
    )
    record = record.stage("analysis", StageStatus.RUNNING)
    record = record.transition(JobStatus.SUCCEEDED, "done")
    assert statuses(record.stages)["analysis"] == StageStatus.DONE
    assert statuses(record.stages)["verifier"] == StageStatus.SKIPPED


def wait(store, job_id):
    for _ in range(200):
        record = store.get(job_id)
        if record.status.terminal:
            return record
        time.sleep(0.01)
    raise AssertionError("job did not finish")


def test_queue_persists_stage_progress_and_marks_failures(tmp_path):
    store = FileJobStore(tmp_path)
    queue = LocalJobQueue(store)

    def good(progress):
        progress("started")
        progress.stage("repository", StageStatus.RUNNING)
        progress.stage("repository", StageStatus.DONE, "o/r @ abc")
        return Done()

    def bad(progress):
        progress.stage("analysis", StageStatus.RUNNING)
        raise RepoAgentError("analysis exploded")

    stages = initial_stages(WorkflowKind.DISCOVER)
    ok = wait(store, queue.submit(JobKind.DISCOVER, "r", good, stages).id)
    failed = wait(store, queue.submit(JobKind.DISCOVER, "r", bad, stages).id)
    queue.shutdown()
    assert ok.status == JobStatus.SUCCEEDED
    assert ok.stages[0].detail == "o/r @ abc" and ok.stages[0].visits == 1
    assert failed.error == "analysis exploded"
    assert statuses(failed.stages)["analysis"] == StageStatus.FAILED
    assert statuses(failed.stages)["repository"] == StageStatus.SKIPPED
