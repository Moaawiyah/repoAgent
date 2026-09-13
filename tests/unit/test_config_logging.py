"""Configuration isolation and metadata-only logs."""

import json
import logging

import pytest
from pydantic import ValidationError

from repoagent.config import Settings
from repoagent.logging import EventFormatter, configure_logging


def test_settings_environment_and_explicit_precedence(monkeypatch, tmp_path):
    monkeypatch.setenv("REPOAGENT_DATA_DIR", str(tmp_path / "env"))
    monkeypatch.setenv("REPOAGENT_MAX_RETRIES", "5")
    assert Settings().max_retries == 5
    assert Settings().data_dir == tmp_path / "env"
    assert Settings(data_dir=tmp_path / "explicit").data_dir == tmp_path / "explicit"


def test_dotenv_requires_explicit_path(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("REPOAGENT_MAX_RETRIES", raising=False)
    env = tmp_path / ".env"
    env.write_text("REPOAGENT_MAX_RETRIES=7\n")
    assert Settings().max_retries == 3
    assert Settings(_env_file=env).max_retries == 7


@pytest.mark.parametrize(
    "values",
    [
        {"max_retries": -1},
        {"context_budget": 0},
        {"execution_timeout": 0},
        {"log_level": "SECRET"},
    ],
)
def test_invalid_settings(values):
    with pytest.raises(ValidationError):
        Settings(**values)


def test_formatter_excludes_payload_and_exception():
    record = logging.LogRecord("repoagent", logging.INFO, "", 1, "secret", (), None)
    record.event = "task_created"
    record.task_id = "123"
    record.description = "private issue"
    record.exc_text = "secret exception"
    data = json.loads(EventFormatter().format(record))
    assert data["event"] == "task_created"
    assert data["task_id"] == "123"
    assert "secret" not in json.dumps(data)
    assert "description" not in data


def test_configure_logging_is_idempotent():
    configure_logging("DEBUG")
    configure_logging("INFO")
    logger = logging.getLogger("repoagent")
    assert len(logger.handlers) == 1
    assert not logger.propagate
    assert logger.level == logging.INFO
