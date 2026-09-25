"""SWE-rebench import and `benchmark-verify` through the SDK and CLI (offline)."""

import json
import shutil

import pytest
from typer.testing import CliRunner

from repoagent import RepoAgent, Settings
from repoagent.benchmark.loaders import BenchmarkError
from repoagent.benchmark.materialize import RepositoryMaterializer
from repoagent.cli.main import app
from tests.support.sandbox import FakeSandboxRunner, execution, pytest_result

GOLD = """diff --git a/calc.py b/calc.py
--- a/calc.py
+++ b/calc.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a - b
+    return a + b
"""
TESTS = """diff --git a/tests/test_calc.py b/tests/test_calc.py
--- a/tests/test_calc.py
+++ b/tests/test_calc.py
@@ -1,2 +1,5 @@
 def test_placeholder():
     assert True
+
+def test_add():
+    assert __import__("calc").add(2, 2) == 4
"""


def record(instance="o__calc-1", test_patch=TESTS):
    return {
        "instance_id": instance,
        "repo": "o/calc",
        "base_commit": "a" * 40,
        "patch": GOLD,
        "test_patch": test_patch,
        "problem_statement": "add() subtracts instead of adding",
        "FAIL_TO_PASS": '["tests/test_calc.py::test_add"]',
        "PASS_TO_PASS": ["tests/test_calc.py::test_placeholder"],
        "install_config": {"python": "3.9", "pip_packages": ["pytest"]},
        "requirements": "six==1.16.0\n-e git+https://github.com/o/calc.git@x#egg=calc\n",
    }


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    if shutil.which("git") is None:
        pytest.skip("git unavailable")
    root = tmp_path / "calc"
    (root / "tests").mkdir(parents=True)
    (root / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    (root / "tests/test_calc.py").write_text(
        "def test_placeholder():\n    assert True\n"
    )
    monkeypatch.setattr(RepositoryMaterializer, "materialize", lambda self, ref: root)
    return root


def test_import_builds_pinned_task_and_reports_skips(tmp_path, checkout):
    api = RepoAgent(settings=Settings(data_dir=tmp_path / "data")).benchmarks()
    broken = record("o__calc-2", TESTS.replace("test_placeholder", "missing"))
    suite, skipped = api.import_swerebench(
        [record(), broken], ["o__calc-1", "o__calc-2"], "python:{python}-slim"
    )
    (task,) = suite.tasks
    assert task.expected_files == ["calc.py"] and task.expected_symbols == ["calc.add"]
    assert "def test_add" in task.validation.hidden_tests["tests/test_calc.py"]
    assert task.validation.fail_to_pass == ["tests/test_calc.py::test_add"]
    assert task.environment.requirements == ["six==1.16.0", "pytest"]
    assert task.environment.image.startswith("python")
    assert "does not apply" in skipped["o__calc-2"]
    with pytest.raises(BenchmarkError):
        api.import_swerebench([broken], ["o__calc-2"], "python:{python}-slim")
    with pytest.raises(BenchmarkError):
        api.import_swerebench([record()], ["unknown"], "python:{python}-slim")


def test_cli_import_then_verify_writes_verified_suite(tmp_path, checkout, monkeypatch):
    rows, suite, verified = (
        tmp_path / "rows.jsonl",
        tmp_path / "s.json",
        tmp_path / "v.json",
    )
    rows.write_text(json.dumps(record()) + "\n")
    base = ["--data-dir", str(tmp_path / "data")]
    result = CliRunner().invoke(
        app,
        [*base, "benchmark-import", "swerebench", str(rows), "--output", str(suite)]
        + ["--item", "o__calc-1"],
    )
    assert result.exit_code == 0, result.output
    red = execution(pytest_result(passed=1, failed=["tests/test_calc.py::test_add"]))
    green = execution(pytest_result(passed=2))
    fake = FakeSandboxRunner(baseline=green, attempts=[red, green])
    monkeypatch.setattr(
        "repoagent.benchmark.environment.DockerSandboxRunner",
        lambda image, workspace_dir=None: fake,
    )
    result = CliRunner().invoke(
        app, [*base, "benchmark-verify", str(suite), "--output", str(verified)]
    )
    assert result.exit_code == 0, result.output
    assert "o__calc-1: VERIFIED" in result.output
    assert [t["task_id"] for t in json.loads(verified.read_text())["tasks"]] == [
        "o__calc-1"
    ]
    failing = FakeSandboxRunner(baseline=red, attempts=[red, green])
    monkeypatch.setattr(
        "repoagent.benchmark.environment.DockerSandboxRunner",
        lambda image, workspace_dir=None: failing,
    )
    as_json = CliRunner().invoke(app, [*base, "benchmark-verify", str(suite), "--json"])
    assert json.loads(as_json.output.splitlines()[0])["verified"] is False
