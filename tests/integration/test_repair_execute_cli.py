"""`repair --execute` CLI through the SDK with fake sandbox and provider."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from repoagent.cli.main import app
from tests.support.execution_provider import ISSUE, ExecutionProvider
from tests.support.sandbox import FakeSandboxRunner, execution, pytest_result

ROOT = Path(__file__).resolve().parents[1] / "fixtures/auth_bug"
runner = CliRunner()
RED = execution(pytest_result(passed=2, failed=["tests/test_login.py::test_upper"]))


@pytest.fixture
def sandbox(monkeypatch):
    fake = FakeSandboxRunner(attempts=[RED, execution(pytest_result(passed=3))])
    monkeypatch.setattr(
        "repoagent.sdk.validated_repair.DockerSandboxRunner",
        lambda image, workspace_dir=None: fake,
    )
    monkeypatch.setattr(
        "repoagent.sdk.validated_repair.llm_provider_from_settings",
        lambda settings: ExecutionProvider(),
    )
    return fake


def invoke(tmp_path, *args):
    return runner.invoke(app, ["--data-dir", str(tmp_path / "data"), *args])


def test_execute_renders_attempt_history(tmp_path, sandbox):
    assert invoke(tmp_path, "index", str(ROOT)).exit_code == 0
    result = invoke(
        tmp_path, "repair", str(ROOT), ISSUE, "--execute", "--max-attempts", "2"
    )
    assert result.exit_code == 0, result.output
    for text in (
        "Baseline",
        "Attempt 1",
        "tests failed",
        "Failure Analyzer",
        "Attempt 2",
    ):
        assert text in result.output
    assert "VALIDATED" in result.output and "not modified" in result.output


def test_execute_json_and_timeout_option(tmp_path, sandbox):
    assert invoke(tmp_path, "index", str(ROOT)).exit_code == 0
    result = invoke(
        tmp_path, "repair", str(ROOT), ISSUE, "--execute", "--json", "--timeout", "42"
    )
    payload = json.loads(result.stdout)
    assert payload["status"] == "validated" and len(payload["attempts"]) == 2
    assert payload["metrics"]["attempts"] == 2 and sandbox.limits.timeout_seconds == 42


def test_failed_validation_exits_nonzero(tmp_path, monkeypatch, sandbox):
    sandbox.script[1:] = [RED]
    assert invoke(tmp_path, "index", str(ROOT)).exit_code == 0
    result = invoke(
        tmp_path, "repair", str(ROOT), ISSUE, "--execute", "--max-attempts", "1"
    )
    assert result.exit_code == 1 and "MAX_ATTEMPTS" in result.output


def test_execution_options_require_execute_flag(tmp_path, sandbox):
    assert invoke(tmp_path, "index", str(ROOT)).exit_code == 0
    result = invoke(tmp_path, "repair", str(ROOT), ISSUE, "--timeout", "5")
    assert result.exit_code == 2 and not sandbox.runs
    bad = invoke(
        tmp_path, "repair", str(ROOT), ISSUE, "--execute", "--max-attempts", "0"
    )
    assert bad.exit_code == 2


def test_repository_without_tests_is_validation_unavailable(tmp_path, sandbox):
    repo = tmp_path / "notests"
    repo.mkdir()
    (repo / "app.py").write_text("def value():\n    return 1\n")
    assert invoke(tmp_path, "index", str(repo)).exit_code == 0
    result = invoke(tmp_path, "repair", str(repo), "value is wrong", "--execute")
    assert result.exit_code == 1 and "VALIDATION_UNAVAILABLE" in result.output
    assert sandbox.opened == 0
