"""Hardened docker arguments and bounded, secret-free host process execution."""

import sys
from pathlib import Path

import pytest

from repoagent.domain.errors import SandboxError
from repoagent.domain.sandbox import SandboxLimits
from repoagent.sandbox import docker_args
from repoagent.sandbox.docker_args import DockerCommandBuilder, container_user
from repoagent.sandbox.process import BoundedCapture, SubprocessRunner

NAME = "repoagent-0123456789abcdef"


def test_validation_container_is_isolated_and_resource_limited(tmp_path):
    limits = SandboxLimits(memory_mb=512, cpus=1.5, pids_limit=64)
    argv = DockerCommandBuilder("python:3.12-slim", limits).run(
        NAME, ["python", "-m", "pytest"], tmp_path / "deps", tmp_path / "ws", False
    )
    joined = " ".join(argv)
    for flag in ("--rm", "--read-only", "--init"):
        assert flag in argv
    assert argv[argv.index("--network") + 1] == "none"
    assert argv[argv.index("--cap-drop") + 1] == "ALL"
    assert "no-new-privileges" in argv and "--memory" in argv and "512m" in argv
    assert argv[argv.index("--pids-limit") + 1] == "64" and "1.5" in argv
    assert f"source={tmp_path / 'deps'},target=/deps,readonly" in joined
    assert f"source={tmp_path / 'ws'},target=/workspace" in joined
    assert "API_KEY" not in joined and "/Users" not in joined.replace(str(tmp_path), "")
    assert argv[-4:] == ["python:3.12-slim", "python", "-m", "pytest"]


@pytest.mark.parametrize(
    "image, name, path",
    [
        ("--privileged", NAME, "/tmp/ok"),
        ("python:3.12", "evil; rm", "/tmp/ok"),
        ("python:3.12", NAME, "/tmp/a,target=/etc"),
    ],
)
def test_invalid_image_name_or_mount_rejected(image, name, path):
    with pytest.raises(SandboxError):
        DockerCommandBuilder(image, SandboxLimits()).run(
            name, ["python"], Path(path), Path("/tmp/ws"), False
        )


def test_container_user_is_never_root(monkeypatch):
    monkeypatch.setattr(docker_args.os, "getuid", lambda: 0)
    assert container_user() == "65534:65534"
    monkeypatch.setattr(docker_args.os, "getuid", lambda: 501)
    monkeypatch.setattr(docker_args.os, "getgid", lambda: 20)
    assert container_user() == "501:20"


def test_bounded_capture_keeps_head_and_tail():
    capture = BoundedCapture(20)
    for _ in range(100):
        capture.feed(b"0123456789")
    text = capture.text()
    assert capture.truncated and text.startswith("0123456789")
    assert text.endswith("0123456789") and "truncated" in text
    small = BoundedCapture(100)
    small.feed(b"short")
    assert small.text() == "short" and not small.truncated


def test_oversized_output_is_truncated_safely():
    code = "import sys; sys.stdout.write('x' * 2_000_000); print('SUMMARY')"
    result = SubprocessRunner().run([sys.executable, "-c", code], 30, 4000)
    assert result.exit_code == 0 and result.truncated
    assert len(result.stdout) < 4200 and result.stdout.rstrip().endswith("SUMMARY")


def test_runaway_process_is_killed_on_timeout():
    code = "import time; time.sleep(30)"
    result = SubprocessRunner().run([sys.executable, "-c", code], 0.5, 4000)
    assert result.timed_out and result.exit_code is None
    assert result.duration_seconds < 10


def test_host_secrets_are_not_forwarded(monkeypatch):
    monkeypatch.setenv("REPOAGENT_LLM_API_KEY", "sk-secret")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "aws-secret")
    code = "import os; print(sorted(os.environ))"
    result = SubprocessRunner().run([sys.executable, "-c", code], 30, 4000)
    assert "REPOAGENT_LLM_API_KEY" not in result.stdout
    assert "AWS_SECRET_ACCESS_KEY" not in result.stdout
