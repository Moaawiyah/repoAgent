"""`repoagent audit` CLI: human/JSON output, --limit, and exit codes."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from repoagent.cli.main import app
from tests.support.scripted import ScriptedLLMProvider

ROOT = Path(__file__).resolve().parents[1] / "fixtures/audit_repo"
runner = CliRunner()
_RESPONSES = [
    {"status": "verified", "reasoning": "TODO left unresolved.", "confidence": 0.6},
    {
        "status": "verified",
        "reasoning": "Cycle confirmed by imports.",
        "confidence": 0.9,
    },
    {
        "status": "uncertain",
        "reasoning": "Cannot confirm reachability.",
        "confidence": 0.4,
    },
    {"status": "rejected", "reasoning": "Literal is safe here.", "confidence": 0.8},
]


@pytest.fixture(autouse=True)
def provider(monkeypatch):
    monkeypatch.setattr(
        "repoagent.sdk.audit.llm_provider_from_settings",
        lambda settings: ScriptedLLMProvider(list(_RESPONSES)),
    )


def invoke(tmp_path, *args):
    return runner.invoke(app, ["--data-dir", str(tmp_path / "data"), *args])


def test_human_output_shows_verified_findings(tmp_path):
    result = invoke(tmp_path, "audit", str(ROOT), "--limit", "4")
    assert result.exit_code == 0
    assert "Repository Audit" in result.output
    assert "Verified:    2" in result.output
    assert "Uncertain:   1" in result.output
    assert "Rejected:    1" in result.output


def test_json_output_matches_report_shape(tmp_path):
    result = invoke(tmp_path, "audit", str(ROOT), "--limit", "4", "--json")
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["metrics"]["candidates_generated"] == 9
    assert len(payload["candidates"]) == 4
    assert {c["status"] for c in payload["candidates"]} == {
        "verified",
        "uncertain",
        "rejected",
    }


def test_invalid_limit_is_input_error(tmp_path):
    result = invoke(tmp_path, "audit", str(ROOT), "--limit", "0")
    assert result.exit_code == 2
