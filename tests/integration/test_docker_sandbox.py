"""Real Docker sandbox run; skipped when no Docker daemon is reachable.

The target repository is deliberately hostile: its own tests assert, from
inside the container, that network, host paths, secrets, root, and writes
outside the workspace are unavailable.
"""

import shutil
import subprocess

import pytest

from repoagent.domain.sandbox import SandboxLimits, SandboxOutcome
from repoagent.sandbox.docker_runner import DockerSandboxRunner
from repoagent.sandbox.workspace import fingerprint
from repoagent.validation.detection import ProjectDetector
from repoagent.validation.evaluator import ValidationEvaluator

IMAGE = "python:3.12-slim"
PATCH = (
    "--- a/app.py\n+++ b/app.py\n@@ -1,2 +1,2 @@\n"
    " def normalize(email):\n-    return email\n+    return email.lower()\n"
)
HOSTILE = """import os, socket
from pathlib import Path
import pytest

def test_network_is_disabled():
    with pytest.raises(OSError):
        socket.create_connection(("1.1.1.1", 53), timeout=3)

def test_host_is_invisible_and_rootfs_readonly():
    assert not Path("{host}").exists()
    assert "SANDBOX_CANARY" not in os.environ and os.getuid() != 0
    with pytest.raises(OSError):
        Path("/etc/repoagent-escape").write_text("x")
"""


def docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        probe = subprocess.run(
            ["docker", "image", "inspect", IMAGE], capture_output=True, timeout=20
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return probe.returncode == 0


pytestmark = pytest.mark.skipif(
    not docker_available(), reason=f"Docker daemon or {IMAGE} image unavailable"
)


def test_baseline_and_patched_validation_in_isolated_container(tmp_path, monkeypatch):
    monkeypatch.setenv("SANDBOX_CANARY", "host-secret")
    repo = tmp_path / "target"
    (repo / "tests").mkdir(parents=True)
    (repo / "pyproject.toml").write_text("[tool.ruff]\n")
    (repo / "app.py").write_text("def normalize(email):\n    return email\n")
    (repo / "tests/test_app.py").write_text(
        "from app import normalize\n\n\ndef test_normalize():\n"
        "    assert normalize('ADA@X.IO') == 'ada@x.io'\n"
    )
    (repo / "tests/test_hostile.py").write_text(HOSTILE.format(host=tmp_path))
    before = fingerprint(repo)
    limits = SandboxLimits(timeout_seconds=180, dependencies="tools")
    plan = ProjectDetector(limits).detect(repo)
    runner = DockerSandboxRunner(IMAGE, workspace_dir=tmp_path / "ws")
    evaluator = ValidationEvaluator()
    with runner.session(repo, plan, limits) as session:
        baseline = evaluator.baseline(session.run(plan.commands, None))
        patched = evaluator.patched(session.run(plan.commands, PATCH), baseline)
    assert baseline.execution.outcome == SandboxOutcome.COMPLETED, baseline.summary
    assert baseline.tests.failing_ids == {"tests/test_app.py::test_normalize"}
    assert baseline.tests.passed == 2
    assert patched.passed, patched.summary + patched.execution.commands[0].stdout
    assert patched.comparison.fixed_failures == ["tests/test_app.py::test_normalize"]
    assert patched.lint is not None and patched.lint.parsed
    assert not patched.comparison.new_lint
    assert patched.execution.cleaned_up and patched.execution.repository_unchanged
    assert fingerprint(repo) == before and "lower" not in (repo / "app.py").read_text()
    assert not any((tmp_path / "ws").iterdir())
