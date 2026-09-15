"""Prompt contexts stay focused: no internal IDs, duplicates, or stale diffs."""

import json
from pathlib import Path

from tests.support.execution_provider import ExecutionProvider, run_repair
from tests.support.sandbox import FakeSandboxRunner, execution, pytest_result

ROOT = Path(__file__).resolve().parents[1] / "fixtures/auth_bug"


def payloads(provider, name):
    return [json.loads(r.user)["untrusted_data"] for r in provider.prompts(name)]


def test_prompts_omit_internal_fields_and_stale_diffs(tmp_path):
    failing = execution(pytest_result(failed=["tests/test_login.py::test_upper"]))
    runner = FakeSandboxRunner(attempts=[failing, execution(pytest_result(passed=3))])
    provider = ExecutionProvider()
    report = run_repair(tmp_path, ROOT, runner, provider)
    assert report.status == "validated"
    assessment = payloads(provider, "evidence_assessment")[0]["evidence"][0]
    assert "chunk_id" not in assessment and "repository_id" not in assessment
    assert {"evidence_id", "file_path", "snippet"} <= set(assessment)
    proposals = payloads(provider, "patch_proposal")
    keys = [(e["file_path"], e["start_line"]) for e in proposals[0]["evidence"]]
    assert len(keys) == len(set(keys)) and "chunk_id" not in proposals[0]["evidence"][0]
    assert "previous_diff" in proposals[1]["runtime_validation_feedback"]
    reviews = payloads(provider, "patch_review")
    assert "previous_diff" not in reviews[1]["runtime_validation_feedback"]
    touched = set(reviews[0]["proposal"]["plan"]["affected_files"])
    cited = set(reviews[0]["primary_hypothesis"]["supporting_evidence"])
    assert all(
        e["file_path"] in touched or e["evidence_id"] in cited
        for e in reviews[0]["evidence"]
    )
    assert len(reviews[0]["evidence"]) <= 6
    assert report.metrics.prompt_chars == sum(
        len(r.system) + len(r.user) for r in provider.requests
    )
