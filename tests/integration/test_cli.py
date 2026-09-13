"""CLI task behavior and inert workflow boundaries."""

import json
import socket
import subprocess
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from repoagent.cli.main import app

runner = CliRunner()


@pytest.fixture
def cli(tmp_path):
    def invoke(*args):
        return runner.invoke(app, ["--data-dir", str(tmp_path / "data"), *args])

    return invoke


@pytest.mark.parametrize("args", [["--help"], ["--version"], ["fix", "--help"]])
def test_help_version_no_side_effects(cli, tmp_path, args):
    result = cli(*args)
    assert result.exit_code == 0, result.output
    assert not (tmp_path / "data").exists()


@pytest.mark.parametrize(
    "command", ["index", "analyze", "ask", "fix", "test", "benchmark"]
)
def test_workflow_is_blocked_and_inert(cli, tmp_path, monkeypatch, command):
    target = tmp_path / "target"
    target.mkdir()
    marker = target / "malicious.py"
    marker.write_text("raise RuntimeError('must not execute')\n")
    before = marker.read_bytes()

    def forbidden(*args, **kwargs):
        raise AssertionError("External execution is forbidden in M1")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    args = [command, "synthetic" if command == "benchmark" else str(target)]
    if command in {"ask", "fix"}:
        args.append("private issue")
    result = cli(*args, "--json")
    assert result.exit_code == 3, result.output
    task = json.loads(result.stdout)
    assert task["status"] == "blocked"
    assert "unavailable in M1" in task["message"]
    assert "private issue" not in result.stderr
    assert marker.read_bytes() == before
    assert list(target.iterdir()) == [marker]
    shown = cli("tasks", "show", task["id"], "--json")
    assert shown.exit_code == 0
    assert json.loads(shown.stdout) == task
    events = cli("tasks", "events", task["id"], "--json")
    assert [e["name"] for e in json.loads(events.stdout)] == [
        "task_created",
        "capability_unavailable",
    ]
    assert "blocked" in cli("tasks", "show", task["id"]).stdout
    assert "capability_unavailable" in cli("tasks", "events", task["id"]).stdout


@pytest.mark.parametrize(
    "args",
    [
        ["index", "/nonexistent-repoagent-source"],
        ["benchmark", "unknown"],
        ["tasks", "show", "invalid-uuid"],
        ["fix", "https://github.com/a/b", " "],
    ],
)
def test_invalid_input_creates_no_storage(cli, tmp_path, args):
    assert cli(*args).exit_code == 2
    assert not (tmp_path / "data").exists()


def test_missing_task_is_operational_error(cli):
    result = cli("tasks", "show", str(uuid4()))
    assert result.exit_code == 1
    assert "Task not found" in result.stderr


def test_invalid_settings_create_no_storage(cli, monkeypatch, tmp_path):
    monkeypatch.setenv("REPOAGENT_MAX_RETRIES", "-1")
    result = cli("benchmark", "synthetic")
    assert result.exit_code == 2
    assert not (tmp_path / "data").exists()


def test_missing_explicit_env_file(cli, tmp_path):
    result = cli("--env-file", str(tmp_path / "missing"), "benchmark", "synthetic")
    assert result.exit_code == 2
    assert not (tmp_path / "data").exists()


def test_storage_failure_is_sanitized(tmp_path):
    target = tmp_path / "secret-path"
    target.write_text("not a directory")
    result = runner.invoke(app, ["--data-dir", str(target), "benchmark", "synthetic"])
    assert result.exit_code == 1
    assert "secret-path" not in result.output
    assert "filesystem operation failed" in result.stderr
