"""CLI analyze behavior against the synthetic fixture repository."""

import json
from pathlib import Path

from typer.testing import CliRunner

from repoagent.cli.main import app

runner = CliRunner()
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "analysis_repo"


def invoke(tmp_path, *args):
    return runner.invoke(app, ["--data-dir", str(tmp_path / "data"), *args])


def test_analyze_prints_text_summary(tmp_path):
    result = invoke(tmp_path, "analyze", str(FIXTURE))
    assert result.exit_code == 0, result.output
    assert "RepoAgent Repository Analysis" in result.output
    assert f"Repository: {FIXTURE.name}" in result.output
    assert "Python files: 6" in result.output
    assert "Classes: 2" in result.output
    assert "Functions: 5" in result.output
    assert "Methods: 4" in result.output
    assert "Tests: 1" in result.output
    assert "File errors: 1" in result.output
    assert "* app/service.py" in result.output


def test_analyze_json_is_machine_readable(tmp_path):
    result = invoke(tmp_path, "analyze", str(FIXTURE), "--json")
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["repository_name"] == FIXTURE.name
    assert data["python_files"] == 6
    assert data["discovered_files"] == 10
    assert data["module_count"] == 5
    assert data["class_count"] == 2
    assert data["method_count"] == 4
    assert data["function_count"] == 5
    assert data["test_count"] == 1
    assert set(data["config_files"]) == {
        "README.md",
        "pyproject.toml",
        "requirements.txt",
    }
    assert not (tmp_path / "data").exists()


def test_analyze_json_contains_symbols_imports_and_relationships(tmp_path):
    data = json.loads(invoke(tmp_path, "analyze", str(FIXTURE), "--json").stdout)
    method = next(
        symbol
        for symbol in data["symbols"]
        if symbol["qualified_name"] == "app.service.UserService.authenticate"
    )
    assert method["parent"] == "app.service.UserService"
    assert [p["name"] for p in method["parameters"]] == ["self", "username", "password"]
    assert method["return_annotation"] == "bool"
    assert method["start_line"] == 9 and method["end_line"] == 11
    async_method = next(
        symbol
        for symbol in data["symbols"]
        if symbol["qualified_name"] == "app.service.UserService.fetch_profile"
    )
    assert async_method["is_async"]
    service = next(
        symbol for symbol in data["symbols"] if symbol["name"] == "UserService"
    )
    assert service["bases"] == ["BaseService"]
    origins = {imp["module"]: imp["origin"] for imp in data["imports"]}
    assert origins["app.base"] == "internal"
    assert origins["os"] == "stdlib"
    assert origins["requests"] == "external"
    kinds = {rel["kind"] for rel in data["relationships"]}
    assert {"imports", "inherits", "contains", "defines"} <= kinds
    inherited = next(rel for rel in data["relationships"] if rel["kind"] == "inherits")
    assert inherited["target"].endswith("BaseService") and inherited["resolved"]


def test_analyze_records_errors_without_failing(tmp_path):
    data = json.loads(invoke(tmp_path, "analyze", str(FIXTURE), "--json").stdout)
    assert len(data["errors"]) == 1
    assert data["errors"][0]["path"] == "broken.py"
    assert data["errors"][0]["error_type"] == "syntax"


def test_analyze_is_deterministic(tmp_path):
    first = invoke(tmp_path, "analyze", str(FIXTURE), "--json").stdout
    second = invoke(tmp_path, "analyze", str(FIXTURE), "--json").stdout
    assert json.loads(first) == json.loads(second)


def test_missing_repository_is_invalid_input(tmp_path):
    result = invoke(tmp_path, "analyze", str(tmp_path / "missing"))
    assert result.exit_code == 2
    assert "existing directory" in result.stderr


def test_file_input_is_invalid(tmp_path):
    target = tmp_path / "file.txt"
    target.write_text("x")
    result = invoke(tmp_path, "analyze", str(target))
    assert result.exit_code == 2


def test_repository_without_python_files_succeeds_empty(tmp_path):
    repo = tmp_path / "docs-only"
    repo.mkdir()
    (repo / "README.md").write_text("# empty\n")
    result = invoke(tmp_path, "analyze", str(repo), "--json")
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["python_files"] == 0
    assert data["module_count"] == 0
    assert data["symbols"] == []
