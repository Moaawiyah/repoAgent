"""DiscoveryGraph routing, verification outcomes and the repair handoff model."""

import pytest

from repoagent.domain.audit import VerificationStatus
from repoagent.domain.audit_report import VerifiedIssue
from repoagent.domain.errors import AuditError, LLMError
from repoagent.domain.workflow import StageStatus
from tests.support.workflows import (
    AUDIT_URL,
    FixtureLoader,
    WorkflowProvider,
    workflow_client,
)

ORDER = [
    "repository",
    "analysis",
    "static_detectors",
    "graph_detectors",
    "deduplicate",
    "evidence",
    "verifier",
    "report",
]


def discover(tmp_path, provider=None, source=AUDIT_URL, limit=None, local=False):
    events = []
    api = workflow_client(tmp_path).workflows(loader=None if local else FixtureLoader())
    result = api.discover(
        source,
        limit=limit,
        provider=provider or WorkflowProvider(),
        progress=lambda key, status, detail="": events.append((key, status, detail)),
    )
    return result, events


def test_discovery_runs_every_stage_and_classifies_findings(tmp_path):
    result, events = discover(tmp_path)
    running = [key for key, status, _ in events if status == StageStatus.RUNNING]
    assert running == ORDER
    done = {key: detail for key, status, detail in events if status == "done"}
    assert done["repository"] == "acme/audit_repo @ aaaaaaaaaaaa"
    assert "candidates" in done["static_detectors"]
    assert done["report"] == f"{len(result.report.candidates)} findings"
    report = result.report
    statuses = {c.status for c in report.candidates}
    assert statuses == {
        VerificationStatus.VERIFIED,
        VerificationStatus.UNCERTAIN,
        VerificationStatus.REJECTED,
    }
    metrics = report.metrics
    assert metrics.verified + metrics.uncertain + metrics.rejected == len(
        report.candidates
    )
    assert metrics.candidates_generated >= len(report.candidates)
    assert metrics.candidates_by_source["circular_dependency"] >= 1
    assert all(c.evidence for c in report.candidates)
    assert all(c.verification.confidence >= 0 for c in report.candidates)
    assert report.repair is None and report.repository == AUDIT_URL
    assert result.usage.llm_calls == len(report.candidates)
    assert len(report.candidates) <= result.limits.discovery_candidates


def test_candidate_limit_bounds_llm_verification(tmp_path):
    provider = WorkflowProvider()
    result, _ = discover(tmp_path, provider=provider, limit=2)
    assert len(result.report.candidates) == 2
    assert len(provider.prompts("audit_verification")) == 2


def test_explicit_zero_limit_is_honored_not_treated_as_unset(tmp_path):
    # limit=0 is falsy in Python; the SDK must not silently fall back to the
    # configured default (`limit or default` would do exactly that).
    result, _ = discover(tmp_path, limit=0)
    assert result.report.candidates == [] and result.usage.llm_calls == 0


def test_clean_repository_skips_evidence_and_verification(tmp_path):
    repo = tmp_path / "clean"
    repo.mkdir()
    (repo / "ok.py").write_text("def add(a: int, b: int) -> int:\n    return a + b\n")
    result, events = discover(tmp_path, provider=None, source=str(repo), local=True)
    running = [key for key, status, _ in events if status == StageStatus.RUNNING]
    assert "verifier" not in running and running[-1] == "report"
    assert result.report.candidates == [] and result.usage.llm_calls == 0


def test_verification_requires_a_provider_when_candidates_exist(tmp_path):
    api = workflow_client(tmp_path).workflows(loader=FixtureLoader())
    with pytest.raises(LLMError, match="No LLM provider"):
        api.discover(AUDIT_URL)


def test_only_verified_findings_convert_to_repair_issues(tmp_path):
    result, _ = discover(tmp_path)
    report = result.report
    verified = report.by_status(VerificationStatus.VERIFIED)[0]
    rejected = report.by_status(VerificationStatus.REJECTED)[0]
    issue = VerifiedIssue.from_report(report, verified.id).to_issue()
    assert verified.file in issue.description and issue.title == verified.title
    with pytest.raises(AuditError, match="Only VERIFIED"):
        VerifiedIssue.from_report(report, rejected.id)
    with pytest.raises(AuditError, match="not found"):
        VerifiedIssue.from_report(report, "0" * 16)
    with pytest.raises(ValueError, match="Only VERIFIED"):
        VerifiedIssue(candidate=rejected)
