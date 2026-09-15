"""Benchmark suite models, loading, experiment configuration and gold labels."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from repoagent import RepoAgent
from repoagent.benchmark.experiment import BenchmarkMode, experiments
from repoagent.benchmark.gold import changed_ranges, expected_files, expected_symbols
from repoagent.benchmark.loaders import (
    BenchmarkError,
    load_suite,
    read_records,
    resolve_suite,
)
from repoagent.benchmark.models import RepositoryRef

ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "benchmarks/fixtures.json"
SHA = "a" * 40
PATCH = """diff --git a/pkg/core.py b/pkg/core.py
--- a/pkg/core.py
+++ b/pkg/core.py
@@ -12,2 +12,3 @@ class X:
-            if user["email"] == email:
+            if user["email"].lower() == email.lower():
diff --git a/tests/test_core.py b/tests/test_core.py
@@ -1 +1,2 @@
+x = 1
"""


def test_committed_fixture_suite_is_valid_and_selectable():
    suite = load_suite(SUITE)
    assert suite.name == "fixtures" and len(suite.tasks) == 6
    assert all(t.validation.hidden_tests and t.gold_patch for t in suite.tasks)
    assert [t.task_id for t in suite.select(["cache-bug"])] == ["cache-bug"]
    with pytest.raises(ValueError, match="Unknown benchmark task"):
        suite.select(["missing"])


@pytest.mark.parametrize(
    "ref",
    [
        {"source": "https://github.com/a/b"},
        {"source": "https://gitlab.com/a/b", "commit": SHA},
        {"source": "https://github.com/a/b", "commit": "abc123"},
        {"source": "https://github.com/a/b;rm", "commit": SHA},
    ],
)
def test_remote_repositories_must_be_pinned_github_commits(ref):
    with pytest.raises(ValidationError):
        RepositoryRef.model_validate(ref)
    assert RepositoryRef(source="https://github.com/a/b.git", commit=SHA).is_remote


def test_resolve_and_read_records(tmp_path, monkeypatch):
    assert resolve_suite(str(SUITE)) == SUITE
    monkeypatch.chdir(ROOT)
    assert resolve_suite("fixtures") == SUITE
    for bad in ("missing", "../etc/passwd", str(tmp_path / "x.json")):
        with pytest.raises(BenchmarkError):
            resolve_suite(bad)
    array, lines = tmp_path / "a.json", tmp_path / "b.jsonl"
    array.write_text(json.dumps([{"id": 1}]))
    lines.write_text('{"id": 1}\n\n{"id": 2}\n')
    assert read_records(array) == [{"id": 1}]
    assert [r["id"] for r in read_records(lines)] == [1, 2]
    with pytest.raises(BenchmarkError):
        load_suite(tmp_path / "missing.json")


def test_experiments_from_ablations():
    arms = experiments(BenchmarkMode.REPAIR, ["full", "no_graph", "no_retry"], k=3)
    assert [a.name for a in arms] == ["full", "no_graph", "no_retry"]
    assert not arms[1].features.graph_retrieval and arms[0].k == 3
    assert experiments(BenchmarkMode.RETRIEVAL, [])[0].name == "full"
    with pytest.raises(ValueError, match="Unknown ablation"):
        experiments(BenchmarkMode.REPAIR, ["bogus"])


def test_gold_labels_are_derived_from_patch(tmp_path):
    assert changed_ranges(PATCH)["pkg/core.py"] == [(12, 13)]
    assert expected_files(PATCH) == ["pkg/core.py"]
    assert expected_files(PATCH, include_tests=True) == [
        "pkg/core.py",
        "tests/test_core.py",
    ]
    fixture = ROOT / "tests/fixtures/auth_bug"
    gold = PATCH.replace("pkg/core.py", "app/users/repository.py").replace(
        "@@ -12,2", "@@ -15,1"
    )
    analysis = RepoAgent().analyze(fixture)
    assert expected_symbols(gold, analysis) == [
        "app.users.repository.UserRepository.find_by_email"
    ]
