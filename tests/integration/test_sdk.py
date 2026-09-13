"""Public SDK persistence, CLI parity, and safe initialization."""

import json
import logging

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from repoagent import RepoAgent, Settings, StorageError, TaskNotFound, TaskStatus
from repoagent.cli.main import app


def test_client_is_lazy_and_does_not_configure_logging(tmp_path):
    data = tmp_path / "data"
    logger = logging.getLogger("repoagent")
    handlers = list(logger.handlers)
    client = RepoAgent(settings=Settings(data_dir=data))
    assert not data.exists()
    with pytest.raises(ValidationError):
        client.fix("https://github.com/a/b", " ")
    with pytest.raises(ValueError):
        client.get_task("not-a-uuid")
    assert not data.exists()
    assert logger.handlers == handlers


@pytest.mark.parametrize("method", ["ask", "fix", "test"])
def test_repository_methods_preserve_typed_inputs(tmp_path, method):
    client = RepoAgent(settings=Settings(data_dir=tmp_path / "data"))
    source = tmp_path / "target"
    source.mkdir()
    args = [source, "An issue or question"] if method in {"ask", "fix"} else [source]
    task = getattr(client, method)(*args, commit="feature/branch")
    assert task.status is TaskStatus.BLOCKED
    assert task.request.kind == method
    assert task.request.repository.commit == "feature/branch"
    assert task.request.repository.source == str(source)
    assert list(source.iterdir()) == []
    assert client.get_task(str(task.id)) == task
    assert [event.sequence for event in client.task_events(task.id)] == [1, 2]


def test_sdk_and_cli_share_persistent_tasks(tmp_path):
    client = RepoAgent(settings=Settings(data_dir=tmp_path))
    task = client.benchmark("synthetic")
    result = CliRunner().invoke(
        app, ["--data-dir", str(tmp_path), "tasks", "show", str(task.id), "--json"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == task.model_dump(mode="json")
    created = CliRunner().invoke(
        app, ["--data-dir", str(tmp_path), "benchmark", "bugsinpy", "--json"]
    )
    assert created.exit_code == 3
    another = RepoAgent(settings=Settings(data_dir=tmp_path))
    assert (
        another.get_task(json.loads(created.stdout)["id"]).request.suite == "bugsinpy"
    )


def test_default_client_respects_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("REPOAGENT_DATA_DIR", str(tmp_path / "data"))
    task = RepoAgent().benchmark("synthetic")
    assert RepoAgent().get_task(task.id) == task


def test_storage_errors_are_public_and_sanitized(tmp_path):
    data = tmp_path / "private-path"
    data.write_text("not a directory")
    client = RepoAgent(settings=Settings(data_dir=data))
    with pytest.raises(StorageError) as failure:
        client.benchmark("synthetic")
    assert "private-path" not in str(failure.value)


def test_missing_task_raises_domain_error(tmp_path):
    client = RepoAgent(settings=Settings(data_dir=tmp_path))
    with pytest.raises(TaskNotFound):
        client.get_task("00000000-0000-0000-0000-000000000000")
