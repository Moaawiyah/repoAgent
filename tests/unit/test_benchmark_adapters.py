"""BugsInPy/SWE-bench importers and the hardened repository materializer."""

import json

import pytest

from repoagent.benchmark.adapters import import_bugsinpy, import_swebench
from repoagent.benchmark.loaders import BenchmarkError
from repoagent.benchmark.materialize import HARDENING, RepositoryMaterializer
from repoagent.benchmark.models import RepositoryRef
from repoagent.domain.errors import RepositoryInvalid
from repoagent.sandbox.process import ProcessResult

SHA = "0123456789abcdef0123456789abcdef01234567"
PATCH = (
    "diff --git a/lib/mod.py b/lib/mod.py\n--- a/lib/mod.py\n+++ b/lib/mod.py\n"
    "@@ -3 +3 @@\n-a\n+b\n"
)


def bugsinpy_tree(root):
    project = root / "projects/demo"
    bug = project / "bugs/1"
    bug.mkdir(parents=True)
    (project / "project.info").write_text('github_url="https://github.com/o/demo/"\n')
    (bug / "bug.info").write_text(
        f'buggy_commit_id="{SHA}"\ntest_file="tests/test_a.py"\n'
    )
    (bug / "bug_patch.txt").write_text(PATCH)
    (bug / "run_test.sh").write_text("pytest -q tests/test_a.py::TestX::test_y")
    return root


def test_import_bugsinpy(tmp_path):
    suite = import_bugsinpy(bugsinpy_tree(tmp_path), ["demo:1"])
    task = suite.tasks[0]
    assert task.task_id == "demo-1" and task.repository.commit == SHA
    assert task.repository.source == "https://github.com/o/demo"
    assert task.expected_files == ["lib/mod.py"] and task.gold_patch == PATCH
    assert task.issue_source == "synthesized_from_failing_tests"
    assert task.validation.fail_to_pass == ["tests/test_a.py::TestX::test_y"]
    with pytest.raises(BenchmarkError):
        import_bugsinpy(tmp_path, ["demo:9"])


def test_import_swebench_records():
    record = {
        "instance_id": "o__r-1",
        "repo": "o/r",
        "base_commit": SHA,
        "problem_statement": "x" * 7000,
        "patch": PATCH,
        "FAIL_TO_PASS": json.dumps(["tests/test_a.py::test_b"]),
        "PASS_TO_PASS": ["tests/test_a.py::test_c"],
    }
    suite = import_swebench([record], ["o__r-1"], "swe-bench-verified", "hf")
    task = suite.tasks[0]
    assert len(task.issue) <= 6000 and task.issue.endswith("[truncated]")
    assert task.validation.fail_to_pass == ["tests/test_a.py::test_b"]
    assert task.validation.pass_to_pass == ["tests/test_a.py::test_c"]
    assert import_swebench([record], [], "swe", "hf").tasks[0].task_id == "o__r-1"
    with pytest.raises(BenchmarkError):
        import_swebench([record], ["missing"], "swe", "hf")


class FakeGit:
    def __init__(self, fail_on=None):
        self.calls, self.fail_on = [], fail_on

    def run(self, argv, timeout, max_output):
        self.calls.append(argv)
        failed = self.fail_on and self.fail_on in argv
        return ProcessResult(1 if failed else 0, "", "", False, False, 0.1)


def test_materializer_local_and_remote(tmp_path):
    local = tmp_path / "suite/repo"
    local.mkdir(parents=True)
    git = FakeGit()
    materializer = RepositoryMaterializer(tmp_path / "cache", tmp_path / "suite", git)
    assert materializer.materialize(RepositoryRef(source="repo")) == local
    with pytest.raises(RepositoryInvalid):
        materializer.materialize(RepositoryRef(source="missing"))
    ref = RepositoryRef(source="https://github.com/o/r.git", commit=SHA)
    target = materializer.materialize(ref)
    assert target.name == f"o__r@{SHA[:12]}" and len(git.calls) == 4
    assert all(call[1 : 1 + len(HARDENING)] == list(HARDENING) for call in git.calls)
    assert ["fetch", "--quiet", "--depth", "1", "origin", SHA] == git.calls[2][-6:]
    materializer.materialize(ref)
    assert len(git.calls) == 4


def test_failed_fetch_cleans_up(tmp_path):
    materializer = RepositoryMaterializer(tmp_path / "c", tmp_path, FakeGit("fetch"))
    ref = RepositoryRef(source="https://github.com/o/r", commit=SHA)
    with pytest.raises(RepositoryInvalid, match="Could not fetch"):
        materializer.materialize(ref)
    assert not any((tmp_path / "c").iterdir())
