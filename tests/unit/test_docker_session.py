"""DockerSandboxRunner orchestration with a fake Docker CLI process."""

from pathlib import Path

import pytest

from repoagent.domain.errors import SandboxError, UnsafeCommandError
from repoagent.domain.sandbox import (
    CleanupPolicy,
    CommandKind,
    CommandSpec,
    DependencyStrategy,
    SandboxLimits,
    SandboxOutcome,
    ValidationPlan,
)
from repoagent.sandbox.docker_runner import DockerSandboxRunner
from repoagent.sandbox.workspace import fingerprint
from tests.support.docker_process import FakeDockerProcess, mount_source
from tests.support.repair_provider import DIFF

ROOT = Path(__file__).resolve().parents[1] / "fixtures/auth_bug"
PYTEST = [CommandSpec(kind=CommandKind.PYTEST)]
PLAN = ValidationPlan(commands=PYTEST, requirements=["pytest>=8,<9"])


def open_session(tmp_path, process, plan=PLAN, **limits):
    runner = DockerSandboxRunner(
        "python:3.12-slim", process=process, workspace_dir=tmp_path / "ws"
    )
    return runner.session(ROOT, plan, SandboxLimits(**limits))


def test_patch_runs_in_copy_and_everything_is_cleaned(tmp_path):
    before, original = fingerprint(ROOT), (ROOT / "app/users/repository.py").read_text()
    process = FakeDockerProcess(outcomes=[(0, ""), (0, "1 passed in 0.1s")])
    with open_session(tmp_path, process) as session:
        deps = mount_source(process.runs()[0], "/deps")
        result = session.run(PYTEST, DIFF)
    install, validation = process.runs()
    assert "--only-binary=:all:" in install and "bridge" in install
    assert mount_source(install, "/workspace") is None
    assert validation[validation.index("--network") + 1] == "none"
    patched = process.seen_files[0]["app/users/repository.py"]
    assert ".lower() == email.lower()" in patched and patched != original
    assert result.outcome == SandboxOutcome.COMPLETED and result.cleaned_up
    assert result.repository_unchanged and fingerprint(ROOT) == before
    assert not process.workspaces[0].exists() and not deps.exists()


def test_failure_and_patch_errors_still_clean_up(tmp_path):
    process = FakeDockerProcess(outcomes=[(0, ""), (1, "1 failed in 0.1s")])
    with open_session(tmp_path, process) as session:
        failed = session.run(PYTEST, DIFF)
        broken = session.run(PYTEST, DIFF.replace('user["email"] ==', "nope =="))
    assert failed.commands[0].exit_code == 1 and failed.cleaned_up
    assert broken.outcome == SandboxOutcome.PATCH_APPLY_FAILED and broken.cleaned_up
    assert not broken.commands and "did not apply" in broken.errors[0]
    assert not any((tmp_path / "ws").iterdir())


def test_keep_failed_workspace_policy(tmp_path):
    process = FakeDockerProcess(outcomes=[(1, "1 failed in 0.1s")])
    keep = CleanupPolicy.KEEP_FAILED_WORKSPACE
    with open_session(tmp_path, process, cleanup=keep, dependencies="none") as s:
        result = s.run(PYTEST, None)
    assert not result.cleaned_up and process.workspaces[0].exists()


def test_timeout_kills_container(tmp_path):
    process = FakeDockerProcess(outcomes=["timeout"])
    with open_session(tmp_path, process, dependencies="none", timeout_seconds=5) as s:
        result = s.run(PYTEST, None)
    assert result.outcome == SandboxOutcome.TIMEOUT and result.commands[0].timed_out
    name = process.runs()[0][process.runs()[0].index("--name") + 1]
    assert ["docker", "rm", "--force", name] in process.calls and result.cleaned_up


def test_docker_level_failure_is_sandbox_error(tmp_path):
    process = FakeDockerProcess(outcomes=[(125, "")])
    with open_session(tmp_path, process, dependencies="none") as session:
        result = session.run(PYTEST, None)
    assert result.outcome == SandboxOutcome.SANDBOX_ERROR and result.cleaned_up


def test_unavailable_daemon_and_failed_install_raise(tmp_path):
    with pytest.raises(SandboxError, match="unavailable"):
        with open_session(tmp_path, FakeDockerProcess(probe_exit=1)):
            pass
    with pytest.raises(SandboxError, match="Dependency preparation"):
        with open_session(tmp_path, FakeDockerProcess(outcomes=[(1, "")])):
            pass
    with pytest.raises(SandboxError, match="Dependency"):
        with open_session(tmp_path, FakeDockerProcess(outcomes=["timeout"])):
            pass
    assert not any((tmp_path / "ws").iterdir())


def test_disallowed_command_rejected_before_docker_is_touched(tmp_path):
    process = FakeDockerProcess()
    plan = ValidationPlan(commands=[CommandSpec(kind=CommandKind.RUFF_CHECK)])
    allowed = frozenset({CommandKind.PYTEST})
    with pytest.raises(UnsafeCommandError):
        with open_session(tmp_path, process, plan, allowed_commands=allowed):
            pass
    assert not process.calls


def test_no_install_without_requirements_or_with_none_strategy(tmp_path):
    process = FakeDockerProcess()
    plan = ValidationPlan(commands=PYTEST)
    with open_session(tmp_path, process, plan, dependencies=DependencyStrategy.TOOLS):
        pass
    assert not process.runs()


class MissingDocker(FakeDockerProcess):
    def __init__(self, fail_on):
        super().__init__()
        self.fail_on = fail_on

    def run(self, argv, timeout, max_output):
        if argv[1] == self.fail_on:
            raise FileNotFoundError("docker")
        return super().run(argv, timeout, max_output)


def test_missing_docker_binary_is_a_sandbox_failure(tmp_path):
    with pytest.raises(SandboxError, match="not installed"):
        with open_session(tmp_path, MissingDocker("version")):
            pass
    with open_session(tmp_path, MissingDocker("run"), dependencies="none") as s:
        result = s.run(PYTEST, None)
    assert result.outcome == SandboxOutcome.SANDBOX_ERROR and result.cleaned_up
