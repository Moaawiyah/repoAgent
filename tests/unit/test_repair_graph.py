"""RepairGraph routing, stage progress and truthful outcomes (SDK level)."""

import pytest

from repoagent.domain.errors import RepositoryInvalid
from repoagent.domain.workflow import StageStatus
from tests.support.workflows import (
    AUTH_URL,
    FixtureLoader,
    WorkflowProvider,
    workflow_client,
)

ISSUE = "Users with uppercase email addresses cannot log in"


class Recorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, StageStatus, str]] = []

    def __call__(self, key, status, detail=""):
        self.events.append((key, status, detail))

    def running(self) -> list[str]:
        keys = [k for k, s, _ in self.events if s == StageStatus.RUNNING]
        return [k for i, k in enumerate(keys) if i == 0 or keys[i - 1] != k]

    def final(self, key) -> StageStatus:
        return [s for k, s, _ in self.events if k == key][-1]


def run(tmp_path, execute=True, **kwargs):
    recorder, loader = Recorder(), FixtureLoader()
    api = workflow_client(tmp_path, **kwargs).workflows(loader=loader)
    result = api.repair(
        AUTH_URL,
        ISSUE,
        execute=execute,
        provider=WorkflowProvider(),
        progress=recorder,
    )
    return result, recorder, loader


def test_validated_repair_walks_every_stage_in_order(tmp_path):
    result, recorder, loader = run(tmp_path)
    assert loader.calls == [AUTH_URL]
    assert result.report.status == "validated" and result.sandbox_validation
    assert result.repository.commit == "a" * 40 and result.index.node_count > 0
    order = recorder.running()
    assert order[:4] == ["repository", "analysis", "investigator", "retrieval"]
    for later in ("developer", "static_validation", "reviewer", "docker_validation"):
        assert later in order
    assert order.index("developer") < order.index("reviewer")
    # The M7 loop runs the Docker baseline first, then validates the patch.
    assert order.index("docker_validation") < order.index("developer")
    assert order[-2:] == ["docker_validation", "report"]
    assert recorder.final("graph") == StageStatus.DONE
    assert recorder.final("docker_validation") == StageStatus.DONE
    assert recorder.final("report") == StageStatus.DONE
    assert result.usage.llm_calls > 0
    assert result.limits.repair_attempts == 3


def test_static_repair_skips_docker_validation(tmp_path):
    result, recorder, _ = run(tmp_path, execute=False)
    assert result.report.status == "approved_for_runtime_validation"
    assert recorder.final("docker_validation") == StageStatus.SKIPPED
    assert "docker_validation" not in recorder.running()


def test_llm_budget_stops_the_workflow_truthfully(tmp_path):
    result, recorder, _ = run(tmp_path, workflow_max_llm_calls=2)
    assert result.report.status == "provider_error"
    assert result.usage.llm_calls == 2
    assert result.report.investigation.termination_reason == "provider_error"
    assert recorder.final("investigator") == StageStatus.FAILED


def test_load_failure_propagates_before_any_analysis(tmp_path):
    def broken(source):
        raise RepositoryInvalid("Could not fetch the repository")

    recorder = Recorder()
    api = workflow_client(tmp_path).workflows(loader=broken)
    with pytest.raises(RepositoryInvalid):
        api.repair(AUTH_URL, ISSUE, provider=WorkflowProvider(), progress=recorder)
    assert recorder.running() == ["repository"]


def test_local_paths_and_missing_directories(tmp_path):
    api = workflow_client(tmp_path).workflows()
    handle = api.open_repository(str(tmp_path))
    assert handle.path == str(tmp_path.resolve()) and handle.commit is None
    with pytest.raises(RepositoryInvalid):
        api.open_repository(str(tmp_path / "missing"))
    with pytest.raises(RepositoryInvalid):
        api.open_repository("https://gitlab.com/o/r")
