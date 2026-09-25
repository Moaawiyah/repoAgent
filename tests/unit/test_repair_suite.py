"""Real-bug repair suite: SWE-rebench import, pinned environments, verification."""

import shutil
from pathlib import Path

import pytest

from repoagent.benchmark.environment import image_digest, task_runner, task_settings
from repoagent.benchmark.loaders import BenchmarkError
from repoagent.benchmark.models import BenchmarkTask, TaskEnvironment
from repoagent.benchmark.rebench import frozen_requirements, hidden_tests
from repoagent.benchmark.verify import verify_task
from repoagent.config import Settings
from repoagent.sandbox.docker_runner import DockerSandboxRunner
from tests.support.sandbox import FakeSandboxRunner, execution, pytest_result

GREEN = execution(pytest_result(passed=3))
RED = execution(pytest_result(passed=2, failed=["tests/test_a.py::test_new"]))
TEST_PATCH = """diff --git a/tests/test_a.py b/tests/test_a.py
--- a/tests/test_a.py
+++ b/tests/test_a.py
@@ -1,2 +1,5 @@
 def test_old():
     assert True
+
+def test_new():
+    assert False
"""


def task(**overrides):
    fields = {
        "task_id": "demo-1",
        "benchmark": "swe-rebench",
        "repository": {"source": "repo"},
        "issue": "Bug",
        "gold_patch": "--- a/m.py\n+++ b/m.py\n",
        "validation": {"hidden_tests": {"tests/test_a.py": "def test_new(): ..."}},
        "environment": {"image": "python:3.9-slim", "requirements": ["six==1.16.0"]},
    }
    return BenchmarkTask.model_validate({**fields, **overrides})


def test_frozen_requirements_keep_pins_and_conda_names_only():
    freeze = (
        "six==1.16.0\npytest @ file:///croot/pytest/work\n"
        "-e git+https://github.com/o/r.git@abc#egg=r\nweird @ https://x/y.whl\n"
    )
    assert frozen_requirements(freeze, ["pytest", "mock"]) == [
        "six==1.16.0",
        "pytest",
        "mock",
    ]


@pytest.mark.skipif(shutil.which("git") is None, reason="git unavailable")
def test_hidden_tests_are_files_after_the_test_patch(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_a.py").write_text("def test_old():\n    assert True\n")
    hidden = hidden_tests(tmp_path, TEST_PATCH)
    assert "def test_new" in hidden["tests/test_a.py"]
    assert "test_new" not in (tmp_path / "tests/test_a.py").read_text()
    with pytest.raises(BenchmarkError, match="apply"):
        hidden_tests(tmp_path, TEST_PATCH.replace("test_old", "test_gone"))
    with pytest.raises(BenchmarkError, match="Python"):
        hidden_tests(tmp_path, TEST_PATCH.replace("test_a.py", "data.json"))


def test_task_environment_overrides_image_and_pins():
    settings = task_settings(Settings(), task())
    assert settings.sandbox_image == "python:3.9-slim"
    assert settings.sandbox_pinned_requirements == ["six==1.16.0"]
    assert task_settings(Settings(), task(environment=None)) == Settings()
    assert isinstance(task_runner(settings, None), DockerSandboxRunner)
    with pytest.raises(ValueError):
        TaskEnvironment(python="python3")


def test_image_digest_is_none_without_docker():
    assert image_digest("python:3.9-slim", docker="/nonexistent/docker") is None


@pytest.mark.parametrize(
    ("script", "verified", "reason"),
    [
        ([GREEN, RED, GREEN], True, None),
        ([RED, RED, GREEN], False, "visible suite fails"),
        ([GREEN, GREEN, GREEN], False, "hidden tests pass on buggy"),
        ([GREEN, RED, RED], False, "gold patch"),
    ],
)
def test_verify_task_requires_all_three_checks(tmp_path, script, verified, reason):
    runner = FakeSandboxRunner(baseline=script[0], attempts=script[1:])
    check = verify_task(task(), Path(tmp_path), Settings(), runner)
    assert check.verified is verified
    assert (check.reason or "").startswith(reason or "")
    assert runner.limits.pinned_requirements == ("six==1.16.0",)
    assert runner.overlays[0] is None and runner.overlays[2] is not None
    assert runner.runs[2][1] == task().gold_patch


def test_verify_task_reports_missing_labels_and_sandbox_errors(tmp_path):
    bare = task(gold_patch=None)
    assert verify_task(bare, tmp_path, Settings(), FakeSandboxRunner()).reason
    broken = FakeSandboxRunner(fail_open="docker down")
    check = verify_task(task(), tmp_path, Settings(), broken)
    assert not check.verified and check.reason == "sandbox: docker down"
