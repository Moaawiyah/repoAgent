"""M6 CLI presents unapplied repair reports through the public SDK."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from repoagent.cli.main import app
from tests.support.repair_provider import RepairProvider

ROOT = Path(__file__).resolve().parents[1] / "fixtures/auth_bug"
ISSUE = "Users with uppercase email addresses cannot log in"
runner = CliRunner()


@pytest.fixture(autouse=True)
def provider(monkeypatch):
    monkeypatch.setattr(
        "repoagent.sdk.repair.llm_provider_from_settings",
        lambda settings: RepairProvider(),
    )


def invoke(tmp_path, *args):
    return runner.invoke(app, ["--data-dir", str(tmp_path / "data"), *args])


def test_repair_json_and_human_output(tmp_path):
    assert invoke(tmp_path, "index", str(ROOT)).exit_code == 0
    human = invoke(tmp_path, "repair", str(ROOT), ISSUE)
    assert human.exit_code == 0 and "not been applied or executed" in human.output
    result = invoke(
        tmp_path, "repair", str(ROOT), ISSUE, "--json", "--max-revisions", "1"
    )
    payload = json.loads(result.stdout)
    assert result.exit_code == 0
    assert payload["status"] == "approved_for_runtime_validation"
    assert payload["validation"]["valid"]


def test_invalid_max_revisions_is_input_error(tmp_path):
    assert invoke(tmp_path, "index", str(ROOT)).exit_code == 0
    result = invoke(tmp_path, "repair", str(ROOT), ISSUE, "--max-revisions", "9")
    assert result.exit_code == 2
