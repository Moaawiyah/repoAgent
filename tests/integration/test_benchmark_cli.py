"""Benchmark CLI commands through the SDK (LLM-free retrieval mode)."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from repoagent.cli.main import app
from repoagent.domain.errors import WorkspaceError
from repoagent.sandbox.patching import write_overlay

ROOT = Path(__file__).resolve().parents[2]
SUITE = str(ROOT / "benchmarks/fixtures.json")
runner = CliRunner()


def invoke(tmp_path, *args):
    return runner.invoke(app, ["--data-dir", str(tmp_path / "data"), *args])


def test_benchmark_run_json_and_report(tmp_path):
    result = invoke(
        tmp_path, "benchmark", SUITE, "--task", "slugify-bug", "--k", "3", "--json"
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    run_id = payload["manifest"]["run_id"]
    assert payload["summary"]["experiments"][0]["tasks_attempted"] == 1
    report = invoke(tmp_path, "benchmark-report", run_id)
    assert report.exit_code == 0 and "RepoAgent Evaluation" in report.stdout
    assert "hybrid_graph  Recall@3" in report.stdout


@pytest.mark.parametrize(
    "args",
    [
        ["benchmark", "no-such-suite"],
        ["benchmark", SUITE, "--ablation", "bogus"],
        ["benchmark", SUITE, "--mode", "chaos"],
    ],
)
def test_invalid_benchmark_input(tmp_path, args):
    assert invoke(tmp_path, *args).exit_code == 2
    assert not (tmp_path / "data").exists()


def test_benchmark_import_commands(tmp_path):
    record = {
        "instance_id": "o__r-1",
        "repo": "o/r",
        "base_commit": "a" * 40,
        "problem_statement": "Bug",
        "patch": "diff --git a/r/x.py b/r/x.py\n",
    }
    source = tmp_path / "records.jsonl"
    source.write_text(json.dumps(record) + "\n")
    output = tmp_path / "suite.json"
    args = ["benchmark-import", "swebench", str(source), "--output", str(output)]
    result = runner.invoke(app, [*args, "--item", "o__r-1"])
    assert result.exit_code == 0 and json.loads(output.read_text())["tasks"]
    bad = runner.invoke(
        app, ["benchmark-import", "other", str(source), "--output", str(output),
              "--item", "x"],
    )  # fmt: skip
    assert bad.exit_code == 1


@pytest.mark.parametrize("path", ["../x.py", "/abs.py", "tests\\x.py", "notes.txt"])
def test_overlay_rejects_unsafe_paths(tmp_path, path):
    with pytest.raises(WorkspaceError):
        write_overlay(tmp_path, {path: "x = 1\n"})
    write_overlay(tmp_path, {"tests/new/test_ok.py": "x = 1\n"})
    assert (tmp_path / "tests/new/test_ok.py").read_text() == "x = 1\n"
