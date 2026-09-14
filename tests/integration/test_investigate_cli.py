"""Investigate CLI behavior with the offline template provider."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from repoagent.cli.main import app

runner = CliRunner()
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "auth_bug"
ISSUE = "Users with uppercase email addresses cannot log in"


@pytest.fixture(autouse=True)
def template_provider(monkeypatch):
    from tests.support.providers import FixtureProvider

    monkeypatch.setattr(
        "repoagent.sdk.investigation.llm_provider_from_settings",
        lambda settings: None if settings.llm_provider == "none" else FixtureProvider(),
    )
    monkeypatch.setenv("REPOAGENT_LLM_PROVIDER", "groq")


def invoke(tmp_path, *args):
    return runner.invoke(app, ["--data-dir", str(tmp_path / "data"), *args])


def index(tmp_path):
    assert invoke(tmp_path, "index", str(FIXTURE)).exit_code == 0


def test_investigate_prints_readable_report(tmp_path):
    index(tmp_path)
    result = invoke(tmp_path, "investigate", str(FIXTURE), ISSUE)
    assert result.exit_code == 0, result.output
    assert "RepoAgent Investigation" in result.output
    assert "Issue:" in result.output
    assert "Termination:" in result.output
    assert "Evidence:" in result.output


def test_investigate_json_is_machine_readable(tmp_path):
    index(tmp_path)
    result = invoke(tmp_path, "investigate", str(FIXTURE), ISSUE, "--json")
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert report["issue"]["description"] == ISSUE
    assert report["termination_reason"] in {
        "confident_root_cause",
        "insufficient_evidence",
        "max_iterations",
    }
    assert report["trace"]
    assert 0.0 <= report["confidence"] <= 1.0
    for item in report["evidence"]:
        assert item["file_path"].endswith(".py")
        assert item["start_line"] >= 1


def test_investigate_preserves_repository(tmp_path):
    before = {
        path: path.read_bytes()
        for path in sorted(FIXTURE.rglob("*"))
        if path.is_file() and ".git" not in path.parts
    }
    index(tmp_path)
    assert (
        invoke(
            tmp_path, "investigate", str(FIXTURE), ISSUE, "--max-iterations", "2"
        ).exit_code
        == 0
    )
    after = {
        path: path.read_bytes()
        for path in sorted(FIXTURE.rglob("*"))
        if path.is_file() and ".git" not in path.parts
    }
    assert before == after


def test_investigate_without_provider_fails_cleanly(tmp_path, monkeypatch):
    monkeypatch.setenv("REPOAGENT_LLM_PROVIDER", "none")
    index(tmp_path)
    result = invoke(tmp_path, "investigate", str(FIXTURE), ISSUE)
    assert result.exit_code == 1
    assert "provider" in result.stderr.lower()


def test_investigate_requires_index(tmp_path):
    result = invoke(tmp_path, "investigate", str(FIXTURE), ISSUE)
    assert result.exit_code == 1
    assert "not been indexed" in result.stderr


def test_investigate_rejects_empty_issue(tmp_path):
    index(tmp_path)
    result = invoke(tmp_path, "investigate", str(FIXTURE), "   ")
    assert result.exit_code == 2
    assert "issue" in result.stderr.lower()


def test_investigate_export_obsidian_note(tmp_path):
    index(tmp_path)
    vault = tmp_path / "vault"
    result = invoke(
        tmp_path,
        "investigate",
        str(FIXTURE),
        ISSUE,
        "--export-obsidian",
        str(vault),
        "--json",
    )
    assert result.exit_code == 0, result.output
    notes = list((vault / "Investigations").glob("investigation-*.md"))
    assert len(notes) == 1
    content = notes[0].read_text(encoding="utf-8")
    assert "## Issue" in content and "## Evidence" in content
    assert "[[" in content


def test_provider_failure_keeps_json_and_exits_one(tmp_path, monkeypatch):
    from tests.support.scripted import ScriptedLLMProvider

    monkeypatch.setattr(
        "repoagent.sdk.investigation.llm_provider_from_settings",
        lambda settings: ScriptedLLMProvider(["not json"]),
    )
    index(tmp_path)
    result = invoke(tmp_path, "investigate", str(FIXTURE), ISSUE, "--json")
    assert result.exit_code == 1
    assert json.loads(result.stdout)["termination_reason"] == "provider_error"
